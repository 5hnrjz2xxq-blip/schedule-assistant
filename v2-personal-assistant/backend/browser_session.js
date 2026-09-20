#!/usr/bin/env node
/**
 * 持久浏览器会话管理器
 * 通过 stdin/stdout 与 Flask 后端通信
 * 
 * 命令:
 *   start    → 启动浏览器，打开登录页，获取验证码
 *   captcha  → 返回验证码图片
 *   login    → 填入验证码并登录
 *   extract  → 提取课表数据
 *   reset    → 重置会话
 *   quit     → 退出
 */

const { chromium } = require('playwright');
const readline = require('readline');

let browser, context, page;
let captchaImage = null;
let status = 'idle';

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

function send(obj) {
    process.stdout.write(JSON.stringify(obj) + '\n');
}

async function startSession() {
    if (browser) return;
    const pw = await chromium.launch({ headless: true });
    browser = pw;
    context = await browser.newContext({
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        viewport: { width: 1920, height: 1080 }
    });
    page = await context.newPage();
}

async function goToLogin() {
    await page.goto('https://ehall.yibinu.edu.cn/authserver/login', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(2000);
    status = 'need_captcha';
}

async function getCaptcha() {
    captchaImage = await page.evaluate(() => {
        const el = document.querySelector('#captchaImg');
        if (!el || el.naturalWidth === 0) return null;
        const c = document.createElement('canvas');
        c.width = el.naturalWidth || el.width;
        c.height = el.naturalHeight || el.height;
        try { c.getContext('2d').drawImage(el, 0, 0); return c.toDataURL('image/png'); }
        catch(e) { return null; }
    });
    return captchaImage;
}

async function doLogin(username, password, captchaCode) {
    try {
        await page.fill('#username', username);
        await page.fill('#password', password);
        await page.waitForTimeout(300);
        await page.evaluate(() => window.encryptPassword());
        await page.waitForTimeout(300);
        
        if (captchaCode) {
            await page.evaluate((code) => {
                const el = document.querySelector('#captchaResponse');
                if (el) el.value = code;
            }, captchaCode);
            await page.waitForTimeout(300);
        }
        
        await page.evaluate(() => document.querySelector('#casLoginForm').submit());
        await page.waitForTimeout(10000);
        
        const err = await page.evaluate(() => {
            const e = document.querySelector('.auth_error:not([style*="display: none"])');
            return e ? e.textContent.trim() : '';
        });
        const url = page.url();
        
        if (err) {
            // 需要新验证码
            await goToLogin();
            const newCaptcha = await getCaptcha();
            return { success: false, error: err, needCaptcha: true, captchaImage: newCaptcha };
        }
        if (url.includes('authserver/login') && !url.includes('ticket=')) {
            await goToLogin();
            const newCaptcha = await getCaptcha();
            return { success: false, error: '登录失败', needCaptcha: true, captchaImage: newCaptcha };
        }
        
        status = 'logged_in';
        return { success: true };
    } catch (e) {
        return { success: false, error: e.message };
    }
}

async function extractCourses() {
    try {
        await page.goto('https://ehall.yibinu.edu.cn/new/index.html', { waitUntil: 'networkidle', timeout: 30000 });
        await page.waitForTimeout(3000);
        await page.goto('https://ehall.yibinu.edu.cn/jwapp/sys/wdkb/*default/index.do#/xskcb', { waitUntil: 'networkidle', timeout: 30000 });
        await page.waitForTimeout(10000);
        
        const courses = await page.evaluate(() => {
            const courses = [];
            const table = document.querySelector('table');
            if (!table) return [];
            const rows = table.querySelectorAll('tr');
            let ps = 0, pe = 0;
            rows.forEach(row => {
                const cells = row.querySelectorAll('td');
                let ci = 0;
                cells.forEach(cell => {
                    const text = cell.textContent.trim();
                    const colspan = parseInt(cell.getAttribute('colspan') || '1');
                    const rowspan = parseInt(cell.getAttribute('rowspan') || '1');
                    if (/^\d{1,2}$/.test(text) && parseInt(text) <= 12 && ci <= 1) {
                        ps = parseInt(text); pe = ps + rowspan - 1;
                    } else if (text.length > 15) {
                        courses.push({ full: text, period_start: ps, period_end: pe, day: ci - 1 });
                    }
                    ci += colspan;
                });
            });
            return courses;
        });
        
        return { success: true, courses: courses, count: courses.length };
    } catch (e) {
        return { success: false, error: e.message };
    }
}

// 命令处理
rl.on('line', async (line) => {
    const [cmd, ...args] = line.trim().split(' ');
    try {
        switch (cmd) {
            case 'start':
                await startSession();
                await goToLogin();
                const captcha = await getCaptcha();
                send({ success: true, status: 'need_captcha', captchaImage: captcha });
                break;
            case 'captcha':
                const newCaptcha = await getCaptcha();
                send({ success: true, captchaImage: newCaptcha });
                break;
            case 'login':
                const [username, password, captchaCode] = args;
                const loginResult = await doLogin(username, password, captchaCode);
                send(loginResult);
                break;
            case 'extract':
                const courseResult = await extractCourses();
                send(courseResult);
                break;
            case 'reset':
                if (page) await page.close().catch(() => {});
                if (context) await context.close().catch(() => {});
                if (browser) await browser.close().catch(() => {});
                browser = context = page = null;
                captchaImage = null;
                status = 'idle';
                send({ success: true });
                break;
            case 'quit':
                if (page) await page.close().catch(() => {});
                if (context) await context.close().catch(() => {});
                if (browser) await browser.close().catch(() => {});
                process.exit(0);
                break;
            default:
                send({ error: `未知命令: ${cmd}` });
        }
    } catch (e) {
        send({ success: false, error: e.message });
    }
});

// 保持进程运行
process.stderr.write('browser_session: ready\n');
