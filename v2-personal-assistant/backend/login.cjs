const { chromium } = require('playwright');
const fs = require('fs');

const LOGIN_URL = 'https://ehall.yibinu.edu.cn/authserver/login';
const SCHEDULE_URL = 'https://ehall.yibinu.edu.cn/jwapp/sys/wdkb/*default/index.do#/xskcb';
const CAPTCHA_FILE = '/tmp/captcha_login.png';
const CODE_FILE = '/tmp/captcha_code.txt';

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

async function main(username, password) {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();

  try {
    // Step 1: Go to login page
    await page.goto(LOGIN_URL, { waitUntil: 'networkidle', timeout: 30000 });

    // Step 2: Get captcha image
    const captchaBase64 = await page.evaluate(() => {
      const img = document.querySelector('#captchaImg');
      if (!img || img.naturalWidth === 0) return null;
      const canvas = document.createElement('canvas');
      canvas.width = img.naturalWidth || img.width;
      canvas.height = img.naturalHeight || img.height;
      const ctx = canvas.getContext('2d');
      try { ctx.drawImage(img, 0, 0); return canvas.toDataURL('image/png'); }
      catch (e) { return null; }
    });

    if (!captchaBase64) {
      // No captcha needed, try login directly
      await page.fill('#username', username);
      await page.fill('#password', password);
      await page.evaluate(() => window.encryptPassword());
      await page.waitForTimeout(500);
      await page.evaluate(() => document.querySelector('#casLoginForm').submit());
      await page.waitForTimeout(8000);
    } else {
      // Save captcha image
      const base64Data = captchaBase64.replace(/^data:image\/png;base64,/, '');
      fs.writeFileSync(CAPTCHA_FILE, Buffer.from(base64Data, 'base64'));
      
      // Print captcha image path (for the caller to show the user)
      console.log(JSON.stringify({ needCaptcha: true, captchaFile: CAPTCHA_FILE }));
      
      // Wait for captcha code file (up to 120 seconds)
      const startTime = Date.now();
      let captchaCode = '';
      while (Date.now() - startTime < 120000) {
        try {
          if (fs.existsSync(CODE_FILE)) {
            captchaCode = fs.readFileSync(CODE_FILE, 'utf-8').trim();
            if (captchaCode) {
              fs.unlinkSync(CODE_FILE);
              break;
            }
          }
        } catch (e) {}
        await new Promise(r => setTimeout(r, 1000));
      }
      
      if (!captchaCode) {
        return { success: false, error: '验证码超时' };
      }

      // Fill credentials and captcha
      await page.fill('#username', username);
      await page.fill('#password', password);
      await page.waitForTimeout(300);
      await page.evaluate(() => window.encryptPassword());
      await page.waitForTimeout(300);
      
      // Fill captcha using JavaScript (element is hidden)
      await page.evaluate((code) => {
        const el = document.querySelector('#captchaResponse');
        if (el) { el.value = code; }
      }, captchaCode);
      
      // Submit
      await page.evaluate(() => document.querySelector('#casLoginForm').submit());
      await page.waitForTimeout(8000);
    }

    // Check login result
    const currentUrl = page.url();
    const errorMsg = await page.evaluate(() => {
      const e = document.querySelector('.auth_error:not([style*="display: none"])');
      return e ? e.textContent.trim() : '';
    });
    
    if (errorMsg) {
      return { success: false, error: errorMsg };
    }
    
    if (currentUrl.includes('authserver/login') && !currentUrl.includes('ticket=')) {
      return { success: false, error: '登录失败' };
    }
    
    // Navigate to schedule
    await page.goto('https://ehall.yibinu.edu.cn/new/index.html', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);
    await page.goto(SCHEDULE_URL, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(8000);
    
    const title = await page.title();
    if (title.includes('统一身份认证')) {
      return { success: false, error: '登录未生效' };
    }
    
    // Extract courses
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
    
    return { success: true, courses: parsed, count: parsed.length };
    
  } finally {
    await browser.close();
  }
}

// CLI
const [u, p] = process.argv.slice(2);
if (!u || !p) { console.error('Usage: node login.cjs <学号> <密码>'); process.exit(1); }
main(u, p).then(r => console.log(JSON.stringify(r))).catch(e => console.error(JSON.stringify({ success: false, error: e.message })));
