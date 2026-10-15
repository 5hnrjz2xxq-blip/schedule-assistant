# 宜宾学院课表助手 🎓

从教务系统一键抓取课表，生成周课表视图并导出 `.ics` 导入苹果日历。解决"每学期初手动抄课表"的痛点。

| 版本 | 目录 | 说明 |
|------|------|------|
| v2（当前） | `v2-personal-assistant/` | Web 界面 + 命令行双模式，Playwright 自动登录（含验证码处理）、课表展示、`.ics` 导出、日历颜色自动分配 |
| v1 | `v1-pa/` | 早期版本（Flask 后端 + 前端页面），保留备查 |

## v2 功能

1. **自动爬取** — Playwright 浏览器自动化登录教务系统抓取课表（验证码触发时前端弹出输入框）
2. **课表展示** — 周课表网格，颜色区分不同课程（`backend/calendar_color.py` 自动检测现有日历颜色、为每门课建独立日历）
3. **苹果日历导入** — 一键导出 `.ics`，双击即导入；也支持命令行直接生成

## 快速开始

```bash
cd v2-personal-assistant
./start.sh                    # 打开 Web 界面 → http://localhost:8080
./start.sh <学号> <密码>       # 直接爬取 + 导出 .ics
```

依赖：Python 3（Flask）、Node.js（Playwright）。`backend/requirements.txt` / `package.json` 已声明。

## 项目结构（v2）

```text
v2-personal-assistant/
├── backend/
│   ├── app.py              # Flask Web 服务
│   ├── scraper_prod.cjs    # Playwright 爬虫（生产版）
│   ├── login.cjs / login_with_captcha.cjs / auto_login.cjs
│   ├── calendar_gen.py     # .ics 生成
│   └── calendar_color.py   # 日历颜色自动分配
├── frontend/index.html     # 周课表 Web 界面
├── iOS/                    # iOS 端（实验性）
└── start.sh                # 一键启动脚本
```

## 🔒 隐私说明

学号与密码仅在运行时由使用者自行输入（命令行参数或网页表单），**仓库中不包含任何真实账号信息**，测试用 `.ics` 文件仅含课程/教师/教室公开信息。
