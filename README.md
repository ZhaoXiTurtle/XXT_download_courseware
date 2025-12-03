# 学习通批量下载课件（带图形界面）
> 实现学习通课件的异步批量快速下载，章节和资料页面均可，带精美UI界面操作简单方便，快来试试！
> 支持账号密码/二维码两种方式登录

## 🪢程序框架
- 爬虫
  - 由python的requests库实现，通过学习通隐藏接口调取课件下载地址，代码使用aiohttp重写异步加快爬取速度
- UI界面
  - html+css实现UI部分，界面简洁
- 服务端
  - fastapi库在中间充当服务器向网页和爬虫实现交互

## 🎇运行截图
- <img width="1126" height="777" alt="截图" src="https://github.com/user-attachments/assets/f2f919c5-9971-44cf-8b98-f984fecb1f91" />




 ## ✨TODO List
- 资料页面递归搜索文件

## 💖留言
- 练手项目，点个star呗🥰
