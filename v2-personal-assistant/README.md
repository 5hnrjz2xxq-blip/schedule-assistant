# 宜宾学院课表助手 🎓

## 一键启动
```bash
cd ~/personal-assistant
./start.sh                    # 打开Web界面
./start.sh 241304104 密码     # 直接爬取+导出.ics
```

浏览器打开 http://localhost:8080

## 功能
1. **自动爬取** — 从教务系统抓取课表（Playwright浏览器自动化）
2. **课表展示** — 周课表网格，颜色区分不同课程
3. **苹果日历导入** — 一键导出.ics文件，双击即导入

## 日历颜色方案
命令行运行一键颜色导入：
```bash
cd ~/personal-assistant
python3 backend/calendar_color.py
```
自动检测现有日历颜色，为每门课分配不同颜色，创建独立日历并导入。

## 学期日期
- 2025-2026学年第二学期：2026年3月2日（可在界面中修改）

## 问题排查
- **验证码**: 多次登录可能触发验证码，前端会自动显示验证码输入框
- **文件锁定**: 项目在 ~/personal-assistant/，不在Desktop下，无文件锁问题
