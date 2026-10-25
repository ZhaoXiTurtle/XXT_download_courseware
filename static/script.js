function encryptByAES(message) {
    const key = "u2oh6Vu^HWe4_AES"
    let CBCOptions = {
        iv: CryptoJS.enc.Utf8.parse(key),
        mode: CryptoJS.mode.CBC,
        padding: CryptoJS.pad.Pkcs7
    };
    let aeskey = CryptoJS.enc.Utf8.parse(key);
    let secretData = CryptoJS.enc.Utf8.parse(message);
    let encrypted = CryptoJS.AES.encrypt(
        secretData,
        aeskey,
        CBCOptions
    );
    return CryptoJS.enc.Base64.stringify(encrypted.ciphertext);
}

let courses_info = {}
let qrcodeInterval = null;
// 页面加载完成后初始化二维码
window.onload = function () {
    // 初始化二维码
    refreshQrcode();
}

// 二维码图片加载失败时的兜底提示（正常情况不该触发：图片是服务端内联的 base64）
function qrImageFailed(img) {
    img.alt = '二维码加载失败，请按 Ctrl+F5 刷新';
    showFloatingAlert('二维码加载失败，请按 Ctrl+F5 强制刷新页面', 'error');
}

// 刷新二维码
async function refreshQrcode() {
    // 清除之前的轮询
    if (qrcodeInterval) {
        clearInterval(qrcodeInterval);
    }

    // 请求新的二维码
    try {
        const response = await fetch('/get_qrcode');
        const data = await response.json();
        if (data.status) {
            // 显示二维码：服务端已把图片按 base64 内联返回，避免浏览器另开
            // 一个 session 去拉 createqr，导致服务端轮询时「会话已失效」
            document.getElementById('QR_img').src = data.qrcode_data || data.qrcode_url;
            document.getElementById('QR_hint').textContent = '用学习通 App 扫码';
            // 稍微等待一下，防止二维码还没访问完就开始轮询
            await new Promise(resolve => setTimeout(resolve, 2000));
            // 开始轮询检查扫码状态
            qrcodeInterval = setInterval(() => checkQrcodeStatus(data.uuid, data.enc), 3000);
        } else {
            document.getElementById('QR_hint').textContent = '获取二维码失败，请刷新页面';
            showFloatingAlert('获取二维码失败', 'error');
        }
    } catch (error) {
        showFloatingAlert('网络错误', 'error');
    }
}

// 检查二维码状态
async function checkQrcodeStatus(uuid, enc) {

    const response = await fetch(`/check_qrcode?uuid=${uuid}&enc=${enc}`);
    const data = await response.json();
    if (data.status) {
        // 登录成功
        clearInterval(qrcodeInterval);
        showFloatingAlert('登录成功', 'success');
        await get_courses();

    } else if (data.mes && data.mes.includes('失效')) {
        // 学习通可能回「二维码已失效」也可能回「会话已失效，请刷新页面重试」，
        // 两种都要换一张新的二维码，否则页面会一直静默轮询下去
        await refreshQrcode();
        showFloatingAlert('二维码已自动刷新', 'success');
    }

}

// 密码登录
async function login() {
    const phone = document.getElementById('phone').value;
    const pwd = document.getElementById('pwd').value;

    const encryptedPhone = encryptByAES(phone);
    const encryptedPwd = encryptByAES(pwd);

    const response = await fetch('/login', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({phone: encryptedPhone, pwd: encryptedPwd})
    });
    const data = await response.json();
    if (data.status) {
        showFloatingAlert('登录成功', 'success');
        // 登录成功
        await get_courses();
    } else {
        showFloatingAlert('登录失败！', 'error');
        return 0;
    }
}

async function get_courses() {
    const response = await fetch('/get_courses');
    const courses_info = await response.json()
    updateUI(courses_info)
}

function updateUI(courses_info) {
    if (qrcodeInterval) {
        clearInterval(qrcodeInterval);
    }
    document.querySelector('.login-container').style.display = 'none';
    document.querySelector('.download-container').style.display = 'block';

    const select = document.getElementById('course-select');
    select.innerHTML = `
            <option value="">--请选择课程--</option>
            ${Object.entries(courses_info).map(([name, url]) =>
        `<option value="${url}">${name}</option>`).join('')}
    `;
}

function toggleDownloadType() {
    const toggleBtn = document.getElementById('toggle-btn');
    if (toggleBtn.textContent === '章节课件') {
        toggleBtn.textContent = '资料课件';
        toggleBtn.value = 'resource'
    } else {
        toggleBtn.textContent = '章节课件';
        toggleBtn.value = 'chapter'
    }
    syncChapterPicker();
}

// ---------- 章节多选 ----------
let chapterCache = {};        // 课程 url -> [{id, title}]
let chapterLoadState = 'idle'; // idle | loading | ok | failed

function currentCourseUrl() {
    return document.getElementById('course-select').value;
}

function syncChapterPicker() {
    const picker = document.getElementById('chapter-picker');
    const type = document.getElementById('toggle-btn').value;
    const url = currentCourseUrl();
    if (type !== 'chapter' || !url) {
        picker.style.display = 'none';
        return;
    }
    picker.style.display = 'block';
    loadChapters(url);
}

function onCourseChange() {
    syncChapterPicker();
}

async function loadChapters(url) {
    const list = document.getElementById('chapter-list');
    const count = document.getElementById('chapter-count');
    if (chapterCache[url]) {
        renderChapters(chapterCache[url]);
        return;
    }
    chapterLoadState = 'loading';
    list.innerHTML = '<p class="hint" style="margin:6px 0">正在获取章节列表…</p>';
    count.textContent = '';
    try {
        const resp = await fetch('/get_chapters?url=' + encodeURIComponent(url));
        const data = await resp.json();
        if (data.status) {
            chapterCache[url] = data.chapters;
            chapterLoadState = 'ok';
            renderChapters(data.chapters);
        } else {
            chapterLoadState = 'failed';
            list.innerHTML = '<p class="hint" style="margin:6px 0;color:#c0392b">获取章节失败：'
                + (data.message || '未知错误') + '</p>'
                + '<p class="hint" style="margin:6px 0">这时仍可点「开始下载」，会按整门课处理。</p>';
            count.textContent = '';
        }
    } catch (e) {
        chapterLoadState = 'failed';
        list.innerHTML = '<p class="hint" style="margin:6px 0;color:#c0392b">获取章节失败：' + e + '</p>';
    }
}

function renderChapters(chapters) {
    const list = document.getElementById('chapter-list');
    if (!chapters.length) {
        list.innerHTML = '<p class="hint" style="margin:6px 0">这门课没有解析到章节</p>';
        return;
    }
    list.innerHTML = chapters.map((c, i) => `
        <label class="chapter-item">
            <input type="checkbox" class="chapter-box" value="${c.id}" checked onchange="updateChapterCount()">
            <span>${i + 1}. ${c.title}</span>
        </label>`).join('');
    document.getElementById('chapter-all').checked = true;
    updateChapterCount();
}

function toggleAllChapters(box) {
    document.querySelectorAll('.chapter-box').forEach(el => { el.checked = box.checked; });
    updateChapterCount();
}

function getSelectedChapters() {
    return Array.from(document.querySelectorAll('.chapter-box'))
        .filter(el => el.checked)
        .map(el => el.value);
}

function updateChapterCount() {
    const boxes = document.querySelectorAll('.chapter-box');
    if (!boxes.length) return;
    const picked = getSelectedChapters().length;
    document.getElementById('chapter-count').textContent =
        `共 ${boxes.length} 章，已选 ${picked} 章`;
    const all = document.getElementById('chapter-all');
    all.checked = picked === boxes.length;
    all.indeterminate = picked > 0 && picked < boxes.length;
}

function confirmDownload() {
    const courseName = document.getElementById('course-select').selectedOptions[0].text;
    const courseUrl = document.getElementById('course-select').value;
    const contentType = document.getElementById('toggle-btn').value;
    const savePathInput = document.getElementById('save-path')
    let savePath = savePathInput.value.replaceAll('"', '')
    if (!savePath) {
        savePath = savePathInput.getAttribute('data-default-value')
    }
    if (!courseUrl) {
        showFloatingAlert('请填写完整信息！', 'error');
        return;
    }

    let chapters = null;
    if (contentType === 'chapter' && chapterLoadState === 'loading') {
        showFloatingAlert('章节列表还在加载，稍等一下再点', 'error');
        return;
    }
    if (contentType === 'chapter' && chapterLoadState === 'ok') {
        chapters = getSelectedChapters();
        if (!chapters.length) {
            showFloatingAlert('请至少勾选一个章节', 'error');
            return;
        }
    }

    courses_info.name = courseName
    courses_info.url = courseUrl
    courses_info.type = contentType
    courses_info.path = savePath
    courses_info.chapters = chapters

    // 设置模态对话框中的内容
    document.getElementById('course-info').textContent = courseName;
    let typeText = contentType === 'chapter' ? '章节课件' : '资料课件';
    if (chapters) {
        typeText += `（已选 ${chapters.length} 章）`;
    } else if (contentType === 'chapter') {
        typeText += '（整门课）';
    }
    document.getElementById('type-info').textContent = typeText;
    document.getElementById('path-info').textContent = savePath;

    // 显示模态对话框
    document.getElementById('confirm-modal').style.display = 'block';
}

async function startDownload() {
    closeModal()
    const btn = document.getElementById('down-btn');
    btn.disabled = true;
    showFloatingAlert('下载中，请稍等', 'success', false);
    const response = await fetch('/download', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(courses_info)
    });


    const data = await response.json();
    closeAlert()
    if (!data.message) {
        showFloatingAlert("课件已成功下载至" + courses_info.path, 'success');
    } else {
        showFloatingAlert('下载失败:' + data.message, 'error');
    }
    btn.disabled = false;
}

function closeModal() {
    document.getElementById('confirm-modal').style.display = 'none';
}

function closeAlert() {
    const alertBox = document.getElementById('floating-alert');
    alertBox.style.display = 'none';
}

function showFloatingAlert(message, type, fadeout = true) {
    console.log({message, type});
    const alertBox = document.getElementById('floating-alert');
    if (fadeout) {
        alertBox.className = `floating-alert alert-${type}`;
        // 动画结束后自动隐藏
        setTimeout(() => {
            alertBox.style.display = 'none';
        }, 2900);
    } else {
        alertBox.className = `floating-alert floating-alert--persistent alert-${type}`;
    }
    alertBox.textContent = message;
    alertBox.style.display = 'block';

}