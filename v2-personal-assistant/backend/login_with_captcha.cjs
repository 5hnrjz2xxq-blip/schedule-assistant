/**
 * 宜宾学院教务系统登录爬虫（带验证码交互）
 * 
 * 用法:
 *   1. 获取验证码: node login_with_captcha.cjs --captcha 学号 密码
 *   2. 验证码图片保存到 /tmp/captcha_latest.png
 *   3. 登录:    node login_with_captcha.cjs 学号 密码 验证码
 *   4. 第二次调用会重用第一次的浏览器上下文
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const LOGIN_URL = 'https://ehall.yibinu.edu.cn/authserver/login';
const SCHEDULE_URL = 'https://ehall.yibinu.edu.cn/jwapp/sys/wdkb/*default/index.do#/xskcb';
const STATE_FILE = '/tmp/yibin_browser_state.json';

// Parse course cell function
function parseCourseCell(text) {
  if (!text || text.length < 5) return null;
  const codeMatch = text.match(/^(\w+)\s+(.+?)\s{2,}/);
  if (!codeMatch) return null;
  const courseCode = codeMatch[1];
  const nameMatch = codeMatch[2].match(/^(.+?)\[(\d+)\]$/);
  const courseName = nameMatch ? nameMatch[1].trim() : codeMatch[2].trim();
  const className = nameMatch ? nameMatch[2] : '';
  const rest = text.substring(codeMatch[0].length).trim();
  const parts = rest.split(/\s{2,}/);
  let teacher = '', scheduleStr = '';
  for (const p of parts) {
    if (p.includes('星期') || p.includes('周')) scheduleStr = p;
    else if (!teacher && !p.includes('节')) teacher = p.trim();
  }
  if (!scheduleStr) scheduleStr = parts[parts.length - 1] || '';
  if (!teacher && parts.length >= 2) teacher = parts[1].trim();
  let dayOfWeek = 0, timeSlot = '', location = '', weekType = '';
  const weekRanges = [];
  if (scheduleStr) {
    scheduleStr.split(',').forEach(seg => {
      const t = seg.trim();
      if (t.includes('星期')) dayOfWeek = parseInt(t.replace('星期', '')) || 0;
      else if (t.includes('节')) timeSlot = t.replace('节', '');
      else if (t.includes('周') && (t.includes('单') || t.includes('双'))) {
        weekType = t.includes('单') ? '单' : '双';
        const m = t.match(/(\d+)-(\d+)/);
        if (m) weekRanges.push({ start: parseInt(m[1]), end: parseInt(m[2]), type: weekType });
      } else if (t.includes('周') && t.includes('-')) {
        const m = t.match(/(\d+)-(\d+)/);
        if (m) weekRanges.push({ start: parseInt(m[1]), end: parseInt(m[2]), type: '' });
      } else if (t.includes('周')) {
        const m = t.match(/(\d+)周/);
        if (m) weekRanges.push({ start: parseInt(m[1]), end: parseInt(m[1]), type: '' });
      } else if (t && !t.includes('节') && !t.includes('星期') && !t.includes('周')) location = t;
    });
  }
  let ws = 1, we = 20;
  if (weekRanges.length > 0) { ws = Math.min(...weekRanges.map(r => r.start)); we = Math.max(...weekRanges.map(r => r.end)); }
  return { course_code: courseCode, course_name: courseName, class_name: className, teacher, location, day_of_week: dayOfWeek, time_slot: timeSlot, week_start: ws, week_end: we, week_type: weekType, week_ranges: weekRanges, raw_schedule: scheduleStr };
}

async function getCaptchaImage(page) {
  return await page.evaluate(() => {
    const img = document.querySelector('#captchaImg');
    if (!img) return null;
    if (!img.complete && img.src) return null;
    if (img.naturalWidth === 0) return null;
    const canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth || img.width;
    canvas.height = img.naturalHeight || img.height;
    const ctx = canvas.getContext('2d');
    try { ctx.drawImage(img, 0, 0); return canvas.toDataURL('image/png'); }
    catch (e) { return null; }
  });
}

async function doLogin(username, password, captchaCode) {
  let context;
  
  // Try to restore saved state
  if (fs.existsSync(STATE_FILE)) {
    try {
      context = await chromium.launchPersistentContext('/tmp/yibin_browser_data', {
        headless: true,
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        viewport: { width: 1920, height: 1080 }
      });
    } catch (e) {
      // Clean up stale state
      try { fs.rmSync('/tmp/yibin_browser_data', { recursive: true, force: true }); } catch(e2) {}
      context = await chromium.launchPersistentContext('/tmp/yibin_browser_data', {
        headless: true,
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        viewport: { width: 1920, height: 1080 }
      });
    }
  } else {
    context = await chromium.launchPersistentContext('/tmp/yibin_browser_data', {
      headless: true,
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
      viewport: { width: 1920, height: 1080 }
    });
  }
  
  const page = await context.newPage();
  
  try {
    await page.goto(LOGIN_URL, { waitUntil: 'networkidle', timeout: 30000 });
    
    // Check captcha
    const captchaBase64 = await getCaptchaImage(page);
    
    if (!captchaCode && captchaBase64) {
      // Save captcha image
      const base64Data = captchaBase64.replace(/^data:image\/png;base64,/, '');
      fs.writeFileSync('/tmp/captcha_latest.png', Buffer.from(base64Data, 'base64'));
      
      // Save state for next call
      fs.writeFileSync(STATE_FILE, JSON.stringify({ username, timestamp: Date.now() }));
      
      return { 
        needCaptcha: true, 
        captchaImage: captchaBase64,
        error: '需要输入验证码，验证码图片已保存到 /tmp/captcha_latest.png'
      };
    }
    
    // Fill credentials
    await page.fill('#username', username);
    await page.fill('#password', password);
    await page.waitForTimeout(300);
    
    // Encrypt password
    await page.evaluate(() => { window.encryptPassword(); });
    await page.waitForTimeout(300);
    
    // Fill captcha
    if (captchaBase64 && captchaCode) {
      await page.evaluate((code) => {
        const el = document.querySelector('#captchaResponse');
        if (el) {
          el.value = code;
          el.dispatchEvent(new Event('input', { bubbles: true }));
        }
      }, captchaCode);
    }
    
    // Submit
    await page.evaluate(() => document.querySelector('#casLoginForm').submit());
    await page.waitForTimeout(8000);
    
    // Check result
    const currentUrl = page.url();
    const errorMsg = await page.evaluate(() => {
      const e = document.querySelector('.auth_error:not([style*="display: none"])');
      return e ? e.textContent.trim() : '';
    });
    
    if (errorMsg) {
      // Clean up state on failure
      try { fs.rmSync(STATE_FILE, { force: true }); } catch(e) {}
      return { success: false, error: errorMsg, needCaptcha: !!captchaBase64 };
    }
    
    if (currentUrl.includes('authserver/login') && !currentUrl.includes('ticket=')) {
      try { fs.rmSync(STATE_FILE, { force: true }); } catch(e) {}
      return { success: false, error: '登录失败，请重试', needCaptcha: !!captchaBase64 };
    }
    
    // Navigate to ehall then schedule
    await page.goto('https://ehall.yibinu.edu.cn/new/index.html', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);
    await page.goto(SCHEDULE_URL, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(8000);
    
    const title = await page.title();
    if (title.includes('统一身份认证')) {
      return { success: false, error: '登录未生效' };
    }
    
    // Extract courses (same logic as scraper_prod.cjs)
    const pageData = await page.evaluate(() => {
      const courses = [];
      const table = document.querySelector('table');
      if (!table) return { courses };
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
          } else if (text.length > 20 && /^\w+\s+.+/.test(text)) {
            courses.push({ full_text: text, period_start: ps, period_end: pe, day_of_week: ci - 1 });
          }
          ci += colspan;
        });
      });
      return { courses };
    });
    
    const parsed = [];
    const seen = new Set();
    for (const raw of pageData.courses) {
      const p = parseCourseCell(raw.full_text);
      if (p && p.course_code) {
        const key = `${p.course_code}_${p.day_of_week}_${p.time_slot}_${raw.period_start}`;
        if (!seen.has(key)) {
          seen.add(key);
          if (p.day_of_week === 0) p.day_of_week = raw.day_of_week || 0;
          if (!p.time_slot) p.time_slot = `${raw.period_start}-${raw.period_end}`;
          parsed.push(p);
        }
      }
    }
    
    // Clean up state
    try { fs.rmSync(STATE_FILE, { force: true }); } catch(e) {}
    
    return { success: true, courses: parsed, count: parsed.length };
    
  } finally {
    await context.close();
    // Clean up temp data
    try { fs.rmSync('/tmp/yibin_browser_data', { recursive: true, force: true }); } catch(e) {}
  }
}

// CLI
const args = process.argv.slice(2);
if (args[0] === '--captcha') {
  doLogin(args[1] || '241304104', args[2] || '', '')
    .then(r => console.log(JSON.stringify(r)))
    .catch(e => console.error(JSON.stringify({ error: e.message })));
} else {
  const [u, p, captcha] = args;
  if (!u || !p) { console.error('Usage: node login_with_captcha.cjs <学号> <密码> [验证码]'); process.exit(1); }
  doLogin(u, p, captcha || '')
    .then(r => console.log(JSON.stringify(r)))
    .catch(e => console.error(JSON.stringify({ success: false, error: e.message })));
}
