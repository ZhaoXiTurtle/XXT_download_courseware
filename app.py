from flask import Flask, request, jsonify, send_file
from XXT_download_file import login_task, download_task
import asyncio
import aiohttp
import atexit  # 用于程序结束时关闭session，flask自带的请求结束时会关闭session
import webbrowser  # 自动打开浏览器
import threading

app = Flask(__name__)
loop = asyncio.new_event_loop()
session = None  # 全局化的session，保证两次请求session一致


def open_browser():
    import time
    time.sleep(1)
    webbrowser.open_new("http://localhost:5000")


def run_async(coro):
    return loop.run_until_complete(coro)


@app.route('/')
def index():
    return send_file('UI.html')


@app.route('/static/icon.ico')
def serve_ico():
    return send_file('static/icon.ico')


@app.route('/static/style.css')
def serve_style():
    return send_file('static/style.css')


@app.route('/static/script.js')
def serve_script():
    return send_file('static/script.js')


@app.route('/login', methods=['POST'])
def login_route():
    global session
    data = request.get_json()
    phone = data.get('phone')
    pwd = data.get('pwd')
    # 判断session状态并创建session
    if session is None or session.closed:
        session = aiohttp.ClientSession(loop=loop)
    result = run_async(login_task(session, phone, pwd))
    if not result["status"]:
        run_async(session.close())
    return jsonify(result)


@app.route('/download', methods=['POST'])
def download_route():
    data = request.get_json()
    global session
    try:
        result = run_async(download_task(session, data['courseUrl'], data['savePath']))
        return jsonify({"message": result})
    except Exception as e:
        # 下载出现问题显示报错信息
        # run_async(session.close())
        return jsonify({"message": str(e)})


# 应用退出时清理资源
def shutdown():
    global session, loop
    if session and not session.closed:
        run_async(session.close())
    loop.call_soon_threadsafe(loop.stop)


atexit.register(shutdown)

if __name__ == '__main__':
    threading.Thread(target=open_browser).start()
    app.run(debug=False, port=5000)
