"""
学习通自动下载课件（异步）
"""

# 所有请求使用with语句进行关闭
import asyncio
import aiohttp
from lxml import etree
import json
import os


PHONE = "加密后的"
PWD = "加密后的"
SAVE_HOME_PATH = r"xxxx"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
}


async def login(session, phone, pwd) -> bool:
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
        return "true" in text


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
    async with session.get(url=course_url, headers=headers) as response:
        # 提取请求参数方便后续进行构造
        url = str(response.url)
        query_string = url.split('?')[1]
        param_list = dict(pair.split("=") for pair in query_string.split('&'))
        params = {
            'courseid': param_list['courseid'],
            'clazzid': param_list['clazzid'],
            'cpi': param_list['cpi'],
            'ut': 's',
            't': param_list['t'],
            'stuenc': param_list['enc']
        }
        return params


async def get_chapter_page(session, params):
    url = "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/studentcourse"
    async with session.get(url, headers=headers, params=params) as response:
        tree = etree.HTML(await response.text())
        knowledgeids: list = tree.xpath("//*[@class='chapter_item']//@id")
        return knowledgeids


async def get_resource_page(session, params):
    url = "https://mooc2-ans.chaoxing.com/mooc2-ans/coursedata/stu-datalist"
    async with session.get(url,headers=headers,params=params) as response:
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


async def download_task(session, course_url, content_type, save_home_path):
    # content_type = chapter / resource
    # 先检查下保存路径有没有问题!
    if not os.path.exists(save_home_path):
        return "保存路径不存在！请重新修改路径"
    else:
        if not os.path.isdir(save_home_path):
            return "保存路径不是正确的目录"
    # 请求指定课程url获取新的请求参数
    params = await get_course_params(session, course_url)
    print("params: ",params)
    # 章节页面需要多一步获取konwledgeid再得到objectid
    if content_type == "chapter":
        # 使用参数构造获取所有章节id的请求
        knowledgeids: list = await get_chapter_page(session, params)
        if not knowledgeids:
            return "未找到有效章节！"
        print("knowledgeids: ", knowledgeids)
        # 每个章节分别发送请求
        objectid_tasks = []
        for knowid in knowledgeids:
            _params = {"courseId": params["courseid"],
                      "knowledgeId": knowid.strip('cur')}
            objectid_tasks.append(get_chapter_objectid(session, _params))
        objectid_list = await asyncio.gather(*objectid_tasks)
    elif content_type == "resource":
        objectid_list = await get_resource_page(session, params)
    if not any(objectid_list):
        return "未找到有效课件！"
    print(objectid_list)

    # 获取下载地址和文件名
    pdf_info_task = []
    for objectid in objectid_list:
        if objectid:
            pdf_info_task.append(get_pdf_info(session,objectid))
    pdf_name_url_list = await asyncio.gather(*pdf_info_task)
    print(pdf_name_url_list)
    # 下载所有文件
    download_tasks = []
    name_url: None | tuple
    for name_url in pdf_name_url_list:
        if name_url:
            filename, pdf_url = name_url
            download_tasks.append(download_pdf(session, save_home_path, filename, pdf_url))
    await asyncio.gather(*download_tasks)


async def main(phone, pwd, path):
    async with aiohttp.ClientSession() as session:
        info = await login_task(session, phone, pwd)
        print(info)
        name = input("输入目标课程的全称：")
        url = info['courses'][name]
        content_type = input("输入要爬取的类型，回车为chapter,1为resource")
        content_type = "chapter" if not content_type else 'resource'
        result = await download_task(session, url, content_type,path)
        print(result)


if __name__ == '__main__':
    asyncio.run(main(PHONE, PWD, SAVE_HOME_PATH))
    print("---END---")
