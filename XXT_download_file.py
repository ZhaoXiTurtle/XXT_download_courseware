"""
学习通自动下载课件（异步）
"""

# 所有请求使用with语句进行关闭
import asyncio
import aiohttp
from lxml import etree
import base64
import json
import os
import re
from pathlib import Path

PHONE = "加密后的"
PWD = "加密后的"
SAVE_HOME_PATH = r"xxxx"
headers = {
    'Origin': 'https://passport2.chaoxing.com',
    'Referer': 'https://passport2.chaoxing.com/login?fid=&newversion=true&refer=https%3A%2F%2Fi.chaoxing.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
}


async def login(session, phone, pwd) -> dict:
    # 学习通固定加密参数登录,获取并保存cookies
    url = 'https://passport2.chaoxing.com/fanyalogin'
    data = {
        'fid': '-1',
        'uname': phone,
        'password': pwd,
        'refer': 'http%3A%2F%2Fi.mooc.chaoxing.com%2Fspace%2Findex%3Ft%3D1713670089611',
        't': 'true',
        'forbidotherlogin': '0',
        'doubleFactorLogin': '0',
        'independentId': '0',
        'independentNameId': '0'
    }
    async with session.post(url=url, data=data, headers=headers) as response:
        # 返回是含status的字典文本格式，直接粗暴判断了
        text = await response.text()
        return {'status': "true" in text}


# 二维码登录相关函数
async def get_qrcode(session) -> dict:
    """获取登录二维码

    注意：学习通把 uuid 绑在“取二维码图片”那个请求的 JSESSIONID 上。
    如果让浏览器直接去拉 createqr，服务端这条 session 就绑不上了，
    之后 getauthstatus/v2 只会回「会话已失效」。
    所以这里必须由服务端自己把图片取回来，以 base64 data URI 交给前端。
    """
    params = {
        'fid': '',
        'newversion': 'true',
        'refer': 'https://i.chaoxing.com',
    }

    for _ in range(2):
        # 获取uuid和enc
        async with session.get(
                'https://passport2.chaoxing.com/login',
                headers=headers,
                params=params
        ) as response:
            text = await response.text()
        tree = etree.HTML(text)
        uuid = tree.xpath("//*[@id='uuid']/@value")
        enc = tree.xpath("//*[@id='enc']/@value")
        if not (uuid and enc):
            continue

        # 用同一个 session 取二维码图片，完成 uuid 与 JSESSIONID 的绑定
        async with session.get(
                'https://passport2.chaoxing.com/createqr',
                headers=headers,
                params={'uuid': uuid[0], 'fid': '-1'},
        ) as img_response:
            img_bytes = await img_response.read()

        if img_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            mime = 'image/png'
        elif img_bytes[:3] == b'\xff\xd8\xff':
            mime = 'image/jpeg'
        else:
            # 拿到的是错误页而不是图片，重来一次
            continue

        b64 = base64.b64encode(img_bytes).decode()
        return {"status": True,
                "enc": enc[0],
                "uuid": uuid[0],
                "qrcode_data": f"data:{mime};base64,{b64}",
                "qrcode_url": f"https://passport2.chaoxing.com/createqr?uuid={uuid[0]}&fid=-1"
                }

    return {"status": False}


async def check_qrcode_status(session, uuid, enc) -> dict:
    """检查二维码扫描状态"""
    data = {
        'enc': enc,
        'uuid': uuid,
        'doubleFactorLogin': '0'
    }

    async with session.post(
            'https://passport2.chaoxing.com/getauthstatus/v2',
            headers=headers,
            data=data
    ) as response:
        # 垃圾学习通这里响应类型是text/html，得手动解析json
        text = await response.text()
        result = json.loads(text)
        return result


async def get_all_course_inf(session) -> dict:
    # 获取所有课程名称和对应的url
    url = "https://mooc2-ans.chaoxing.com/mooc2-ans/visit/courselistdata"
    data = {
        'courseType': '1',
        'courseFolderId': '0',
        'query': '',
        'pageHeader': '-1',
        'single': '0',
        'superstarClass': '0',
    }
    async with session.post(url, headers=headers, data=data) as response:
        tree = etree.HTML(await response.text())
        courses_info: dict = {}
        courses_xpath = tree.xpath(f"//div[@class='course-info']//a")
        for course_xpath in courses_xpath:
            course_url = course_xpath.xpath(f"./@href")[0]
            course_name = course_xpath.xpath(f"./span/text()")[0]
            courses_info[course_name] = course_url
        return courses_info


async def get_course_params(session, course_url):
    """从课程链接（跟随跳转后的最终地址）里取 courseid/clazzid/cpi/t/enc。

    学习通不同版本的课程链接参数不一样：老链接是
    ?courseid=&clazzid=&cpi=&enc=&t=，新版本常常只剩 ?courseid=&clazzid=&enc=。
    上游直接 param_list['cpi'] 会抛 KeyError —— 这是「下载失败」最常见的原因之一。
    这里改成「地址栏优先、页面正文兜底、实在没有就留空」。
    """
    async with session.get(url=course_url, headers=headers) as response:
        final_url = str(response.url)
        page = await response.text()

    query_string = final_url.split('?', 1)[1] if '?' in final_url else ''
    param_list = {}
    for pair in query_string.split('&'):
        if '=' in pair:
            k, v = pair.split('=', 1)
            param_list[k] = v

    def pick(*names):
        for name in names:
            if param_list.get(name):
                return param_list[name]
            found = re.search(rf'{name}=([^&"\'\s>]+)', page)
            if found:
                return found.group(1)
        return ''

    return {
        'courseid': pick('courseid'),
        'clazzid': pick('clazzid'),
        'cpi': pick('cpi'),
        'ut': 's',
        't': pick('t'),
        'stuenc': pick('enc', 'stuenc'),
    }


CHAPTER_PAGE_URL = "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/studentcourse"


async def _fetch_chapter_page(session, params):
    async with session.get(CHAPTER_PAGE_URL, headers=headers, params=params) as response:
        return etree.HTML(await response.text())


def _iter_chapter_nodes(tree):
    """返回章节节点。学习通改版过几次，节点 id 从 cur123 变过，这里两种都认。"""
    nodes = tree.xpath("//*[@class='chapter_item']")
    if nodes:
        return nodes
    # 兜底：老页面是一层嵌套，直接取带 cur 前缀的 id
    return [node for node in tree.xpath("//*[@id]") if str(node.get('id', '')).startswith('cur')]


def _chapter_id(node):
    candidates = [node.get('id')] + node.xpath(".//@id")
    for raw in candidates:
        if not raw:
            continue
        found = re.search(r'(\d{5,})', str(raw))
        if found:
            return found.group(1)
    return None


def _chapter_title(node):
    for expr in (".//*[@class='chapter_title']//text()",
                 ".//*[@class='chapter_text']/@title",
                 ".//@title"):
        values = [v.strip() for v in node.xpath(expr) if isinstance(v, str) and v.strip()]
        if values:
            return ' '.join(values)[:80]
    text = ' '.join(t.strip() for t in node.xpath(".//text()") if t.strip())
    return text[:80]


async def get_chapter_page(session, params):
    """返回整门课的章节 id 列表（兼容老调用）。"""
    tree = await _fetch_chapter_page(session, params)
    ids, seen = [], set()
    for node in _iter_chapter_nodes(tree):
        cid = _chapter_id(node)
        if cid and cid not in seen:
            seen.add(cid)
            ids.append(cid)
    return ids


async def get_chapter_list(session, course_url) -> dict:
    """给前端用的章节清单：[{id, title}]，供用户勾选部分章节下载。"""
    try:
        params = await get_course_params(session, course_url)
    except Exception as exc:
        return {"status": False, "message": f"解析课程参数失败（{type(exc).__name__}: {exc}）"}

    if not params.get('courseid') or not params.get('clazzid'):
        return {"status": False, "message": "没能从课程链接里解析出 courseid/clazzid，可能是登录态失效了，请重新登录"}

    tree = await _fetch_chapter_page(session, params)
    chapters, seen = [], set()
    for node in _iter_chapter_nodes(tree):
        cid = _chapter_id(node)
        if not cid or cid in seen:
            continue
        seen.add(cid)
        title = _chapter_title(node) or f"章节 {cid}"
        chapters.append({"id": cid, "title": title})

    if not chapters:
        return {"status": False,
                "message": "章节页里没解析到 chapter_item，可能是登录态失效或页面结构又变了"}
    return {"status": True, "chapters": chapters, "count": len(chapters)}


async def get_resource_page(session, params):
    url = "https://mooc2-ans.chaoxing.com/mooc2-ans/coursedata/stu-datalist"
    async with session.get(url, headers=headers, params=params) as response:
        tree = etree.HTML(await response.text())
        # 拿到所有课件的objectid
        objectid_list: list = tree.xpath("//ul/@objectid")
        return objectid_list


async def get_chapter_objectid(session, _params):
    # 拿到32位objectid参数
    url = "https://mooc1.chaoxing.com/mooc-ans/nodedetailcontroller/visitnodedetail"
    async with session.get(url, headers=headers, params=_params) as response:
        info = etree.HTML(await response.text()).xpath('//iframe/@data')
        if len(info) != 0:
            objectid = json.loads(info[0])['objectid']
            return objectid
        else:
            return None


async def get_pdf_info(session, objectid):
    # 通过objectid构建请求，获取pdf的最终下载链接
    url = f"https://mooc1.chaoxing.com/ananas/status/{objectid}"
    # 这里必须指明referer
    _headers = {
        "Referer": "https://mooc1.chaoxing.com/ananas/modules/video/index.html?v=2024-1128-1842",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 "
                      "Safari/537.36",
    }
    async with session.get(url, headers=_headers) as response:
        res = await response.json()
    if "pdf" in res.keys():
        return res['filename'], res['pdf']
    else:
        return None


async def download_pdf(session, save_home_path, filename: str, pdf_url: str):
    # 判断文件名后缀是否正确,以url后缀为准
    url_extension = pdf_url.rsplit('.', 1)[-1]
    if url_extension not in filename:
        filename = filename.rsplit('.', 1)[0] + '.' + url_extension
    # 通过下载链接下载pdf，这里使用分块下载
    async with session.get(pdf_url, headers=headers) as response:
        path = fr"{save_home_path}\{filename}"
        with open(path, 'wb') as fp:
            print(f'下载中:{filename}')
            while True:
                chunk = await response.content.read(1024)
                if not chunk:
                    break
                fp.write(chunk)


# 下面为封装函数
async def login_task(session, phone, pwd):
    # 登录保存状态
    login_status = await login(session, phone, pwd)
    if not login_status:
        return {"status": False}
    # 获取所有课程info:{name:url}
    courses_info = await get_all_course_inf(session)
    return {"status": True, "courses": courses_info}


async def download_task(session, course_url, content_type, save_home_path, chapter_ids=None):
    # content_type = chapter / resource
    # chapter_ids: 只下这几章（前端勾选的结果）；为空则整门课
    # 先检查下保存路径有没有问题!
    # 如果有扩展名视为文件路径
    if os.path.isfile(save_home_path) or os.path.splitext(save_home_path)[1]:
        return "请提供文件夹路径，而非文件路径！"
    # 不存在就新建
    if not os.path.exists(save_home_path):
        try:
            os.makedirs(save_home_path)
        except OSError as e:
            return f"无法创建新目录:{e}"

    # 先探一下这个目录到底能不能写：否则要等整门课的链接都取完，才在写第一个文件时炸
    probe_path = os.path.join(save_home_path, '.xxt_write_test')
    try:
        with open(probe_path, 'wb') as probe:
            probe.write(b'0')
        os.remove(probe_path)
    except OSError as e:
        return (f"保存目录不可写（{type(e).__name__}: {e}）\n"
                f"可能原因：① 同名的文件正在被其他程序占用；"
                f"② 被 Windows「受控文件夹访问」这类安全策略拦截；③ 当前用户对目录没有写权限。\n"
                f"建议换一个自己新建的、确认可写的目录再试。")
    # 请求指定课程url获取新的请求参数
    params = await get_course_params(session, course_url)
    print("params: ", params)
    if not params.get('courseid') or not params.get('clazzid'):
        return "没能从课程链接里解析出 courseid/clazzid，请重新登录后再试"
    # 章节页面需要多一步获取konwledgeid再得到objectid
    if content_type == "chapter":
        if chapter_ids:
            knowledgeids = [str(cid).strip() for cid in chapter_ids if str(cid).strip()]
            print("用户勾选的章节: ", knowledgeids)
        else:
            # 使用参数构造获取所有章节id的请求
            knowledgeids = await get_chapter_page(session, params)
            print("knowledgeids: ", knowledgeids)
        if not knowledgeids:
            return "未找到有效章节！"
        # 每个章节分别发送请求
        objectid_tasks = []
        for knowid in knowledgeids:
            _params = {"courseId": params["courseid"],
                       "knowledgeId": str(knowid).strip('cur')}
            objectid_tasks.append(get_chapter_objectid(session, _params))
        objectid_list = await asyncio.gather(*objectid_tasks, return_exceptions=True)
    elif content_type == "resource":
        objectid_list = await get_resource_page(session, params)
    else:
        return f"未知的下载类型: {content_type}"

    if not any(x for x in objectid_list if isinstance(x, str)):
        return "未找到有效课件！"
    print(objectid_list)

    # 获取下载地址和文件名
    pdf_info_task = []
    for objectid in objectid_list:
        if objectid and isinstance(objectid, str):
            pdf_info_task.append(get_pdf_info(session, objectid))
    pdf_name_url_list = await asyncio.gather(*pdf_info_task, return_exceptions=True)
    print(pdf_name_url_list)
    # 下载所有文件
    download_tasks = []
    name_url: None | tuple
    for name_url in pdf_name_url_list:
        if isinstance(name_url, tuple) and len(name_url) == 2:
            filename, pdf_url = name_url
            download_tasks.append(download_pdf(session, save_home_path, filename, pdf_url))
    if not download_tasks:
        return "没找到可下载的 PDF：这门课的课件可能不是 PDF 格式（当前只支持 PDF）"

    results = await asyncio.gather(*download_tasks, return_exceptions=True)
    ok = sum(1 for r in results if not isinstance(r, BaseException))
    failed = [r for r in results if isinstance(r, BaseException)]
    print(f"下载完成 {ok} 个，失败 {len(failed)} 个")
    if ok == 0:
        first = failed[0] if failed else "未知错误"
        return f"下载全部失败（{type(first).__name__}: {first}）"
    if failed:
        first = failed[0]
        return f"部分文件失败（{ok} 成功 / {len(failed)} 失败，首个错误 {type(first).__name__}: {first}）"
    return None


async def main(phone, pwd, path):
    async with aiohttp.ClientSession() as session:
        info = await login_task(session, phone, pwd)
        print(info)
        name = input("输入目标课程的全称：")
        url = info['courses'][name]
        content_type = input("输入要爬取的类型，回车为chapter,1为resource")
        content_type = "chapter" if not content_type else 'resource'
        result = await download_task(session, url, content_type, path)
        print(result)


if __name__ == '__main__':
    asyncio.run(main(PHONE, PWD, SAVE_HOME_PATH))
    print("---END---")
