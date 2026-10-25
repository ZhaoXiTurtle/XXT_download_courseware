from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from XXT_download_file import (login, download_task, get_qrcode, check_qrcode_status,
                               get_all_course_inf, get_chapter_list)
import aiohttp
# import asyncio
import traceback
import webbrowser
import threading


# 使用 lifespan 事件处理程序来管理资源的启动和关闭
@asynccontextmanager
async def lifespan(app: FastAPI):
    global session
    session = aiohttp.ClientSession()
    try:
        yield
    finally:
        if session:
            await session.close()


app = FastAPI(lifespan=lifespan)
session = None  # 全局的aiohttp session


# 自定义依赖项来管理aiohttp session
async def get_session():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession()
    return session


# 使用依赖项装饰器来注入session
@app.get("/", response_class=HTMLResponse)
async def read_root():
    return FileResponse('UI.html')


app.mount("/static", StaticFiles(directory="static"), name="static")


# 改了前端文件后浏览器老吃缓存，会出现「代码已修但页面还是旧的」，
# 静态资源统一禁掉缓存（本地小工具，每次重新校验的开销可以忽略）
@app.middleware("http")
async def no_static_cache(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


# 二维码登录相关路由
@app.get("/get_qrcode")
async def get_qrcode_route(session: aiohttp.ClientSession = Depends(get_session)):
    result = await get_qrcode(session)
    return JSONResponse(content=result)


@app.get("/check_qrcode")
async def check_qrcode_route(uuid: str, enc: str, session: aiohttp.ClientSession = Depends(get_session)):
    result = await check_qrcode_status(session, uuid, enc)
    return JSONResponse(content=result)


@app.post("/login")
async def login_route(request: Request, session: aiohttp.ClientSession = Depends(get_session)):
    data = await request.json()
    phone = data.get("phone")
    pwd = data.get("pwd")
    result = await login(session, phone, pwd)
    return JSONResponse(content=result)


@app.get("/get_courses")
async def get_courses_route(session: aiohttp.ClientSession = Depends(get_session)):
    result = await get_all_course_inf(session)
    return JSONResponse(content=result)


# 章节清单：前端用来做「选哪些章」的多选列表
@app.get("/get_chapters")
async def get_chapters_route(url: str, session: aiohttp.ClientSession = Depends(get_session)):
    try:
        result = await get_chapter_list(session, url)
        return JSONResponse(content=result)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"status": False,
                                     "message": f"{type(e).__name__}: {e}"})


@app.post("/download")
async def download_route(request: Request, session: aiohttp.ClientSession = Depends(get_session)):
    data = await request.json()
    courseUrl = data.get("url")
    content_type = data.get("type")
    savePath = data.get("path")
    chapters = data.get("chapters") or None
    try:
        result = await download_task(session, courseUrl, content_type, savePath, chapters)
        return JSONResponse(content={"message": result})
    except Exception as e:
        # 控制台留下完整堆栈，页面只回一句可读的原因
        traceback.print_exc()
        return JSONResponse(content={"message": f"{type(e).__name__}: {e}"})


def open_browser():
    import time
    time.sleep(1)
    webbrowser.open_new("http://localhost:5000")


if __name__ == '__main__':
    threading.Thread(target=open_browser).start()
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
