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
            // 显示二维码
            document.getElementById('QR_img').src = data.qrcode_url;
            // 稍微等待一下，防止二维码还没访问完就开始轮询
            await new Promise(resolve => setTimeout(resolve, 2000));
            // 开始轮询检查扫码状态
            qrcodeInterval = setInterval(() => checkQrcodeStatus(data.uuid, data.enc), 3000);
        } else {
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

    } else if (data.mes === "二维码已失效") {
        // debugger
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

    courses_info.name = courseName
    courses_info.url = courseUrl
    courses_info.type = contentType
    courses_info.path = savePath

    // 设置模态对话框中的内容
    document.getElementById('course-info').textContent = courseName;
    document.getElementById('type-info').textContent = contentType;
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