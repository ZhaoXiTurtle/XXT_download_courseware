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
        body: JSON.stringify({ phone: encryptedPhone, pwd: encryptedPwd })
    });
    // 最后把响应发给页面处理函数
    updateUI(await response.json());
}

function updateUI(data) {
    if (data.status) {
        showFloatingAlert('登录成功','success');
    }
    else {
        showFloatingAlert('登录失败！', 'error');
        return;
    }

    document.querySelector('.login-container').style.display = 'none';
    document.querySelector('.download-container').style.display = 'block';

    const select = document.getElementById('course-select');
    select.innerHTML = `
            <option value="">--请选择课程--</option>
            ${Object.entries(data.courses).map(([name, url]) =>
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

async function startDownload() {
    const courseUrl = document.getElementById('course-select').value;
    const content_type = document.getElementById('toggle-btn').value;
    const savePath = document.getElementById('save-path').value.replaceAll('"', ''); // 删除双引号
    const alertBox = document.getElementById('alert-box');
    const btn = document.getElementById('down-btn');
    if (!courseUrl || !savePath) {
        showFloatingAlert('请填写完整信息！', 'error');
        return;
    }
    btn.disabled = true;
    showFloatingAlert('开始下载：' + content_type + '页面，请稍等', 'success');
    const response = await fetch('/download', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ courseUrl, content_type, savePath })
    });

    const data = await response.json();
    if (!data.message){
        showFloatingAlert("课件已成功下载至" + savePath,'success');
    }
    else{
        showFloatingAlert('下载失败:' + data.message,'error');
    }
    btn.disabled = false;
}

function showFloatingAlert(message, type) {
    const alertBox = document.getElementById('floating-alert');
    alertBox.className = `floating-alert alert-${type}`;
    alertBox.textContent = message;
    alertBox.style.display = 'block';

    // 动画结束后自动隐藏
    setTimeout(() => {
        alertBox.style.display = 'none';
    }, 2900);
}