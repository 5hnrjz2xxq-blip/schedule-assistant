const { chromium } = require('playwright');

const LOGIN_URL = 'https://ehall.yibinu.edu.cn/authserver/login';
const SCHEDULE_URL = 'https://ehall.yibinu.edu.cn/jwapp/sys/wdkb/*default/index.do#/xskcb';

/* ... parseCourseCell same as before ... */
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

/**
 * Get captcha image from the login page
 * Returns base64 of captcha image, or null if no captcha required
 */
async function getCaptchaImage(page) {
  // The captcha image is inside #hidenCaptchaDiv which is display:none
  // We need to extract it regardless
  const captchaData = await page.evaluate(() => {
    const img = document.querySelector('#captchaImg');
    if (!img) return null;
    
    // Force image to load if not already
    if (!img.complete && img.src) {
      return { loading: true, src: img.getAttribute('src') };
    }
    
    if (img.naturalWidth === 0) return { empty: true };
    
    // Draw to canvas even if hidden
    const canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth || img.width;
    canvas.height = img.naturalHeight || img.height;
    const ctx = canvas.getContext('2d');
    try {
      ctx.drawImage(img, 0, 0);
      return canvas.toDataURL('image/png');
    } catch (e) {
      return { error: e.message, src: img.src };
    }
  });
  
  if (!captchaData) return null;
  if (typeof captchaData === 'string') return captchaData; // base64
  if (captchaData.loading) return null; // still loading
  if (captchaData.empty) return null;
  if (captchaData.src) {
    // Try fetching the image directly via page
    try {
      const response = await page.goto(captchaData.src.startsWith('http') ? captchaData.src : 
        'https://ehall.yibinu.edu.cn/authserver/' + captchaData.src, { timeout: 5000 });
      if (response && response.ok()) {
        const buffer = await response.body();
        return 'data:image/png;base64,' + Buffer.from(buffer).toString('base64');
      }
    } catch (e) {}
  }
  return null;
}

async function scrapeCourses(username, password, captchaCode = '') {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();

  try {
    await page.goto(LOGIN_URL, { waitUntil: 'networkidle', timeout: 30000 });
    
    // Check if captcha is required
    const captchaBase64 = await getCaptchaImage(page);
    
    // Fill credentials
    await page.fill('#username', username);
    await page.fill('#password', password);
    await page.waitForTimeout(500);
    await page.evaluate(() => { window.encryptPassword(); });
    await page.waitForTimeout(500);
    
    // Fill captcha if needed
    if (captchaBase64) {
      if (!captchaCode) {
        return {
          success: false,
          needCaptcha: true,
          captchaImage: captchaBase64,
          error: '需要输入验证码'
        };
      }
      await page.fill('#captchaResponse', captchaCode);
    }
    
    // Submit form via JavaScript
    await page.evaluate(() => document.querySelector('#casLoginForm').submit());
    await page.waitForTimeout(5000);
    
    // Check if we got a ticket (success) or error
    const currentUrl = page.url();
    const errorMsg = await page.evaluate(() => {
      const e = document.querySelector('.auth_error:not([style*="display: none"])');
      return e ? e.textContent.trim() : '';
    });
    
    if (errorMsg.includes('验证码') || errorMsg.includes('verification')) {
      return { 
        success: false, 
        needCaptcha: true,
        captchaImage: captchaBase64,
        error: '需要输入验证码' 
      };
    }
    
    if (errorMsg) {
      return { success: false, error: errorMsg, needCaptcha: !!captchaBase64 };
    }
    
    // If still on login page with no error, redirect didn't happen
    if (currentUrl.includes('authserver/login') && !currentUrl.includes('ticket=')) {
      return { success: false, error: '登录失败，请重试', needCaptcha: !!captchaBase64 };
    }
    
    // Navigate to ehall main to establish cookies
    await page.goto('https://ehall.yibinu.edu.cn/new/index.html', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);
    
    // Navigate to schedule
    await page.goto(SCHEDULE_URL, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(8000);
    
    const title = await page.title();
    
    // If bounced back to login, session didn't take
    if (title.includes('统一身份认证')) {
      return { success: false, error: '登录未生效，请检查用户名和密码' };
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

// CLI: extract captcha image only
async function getCaptchaAction(username, password) {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await ctx.newPage();
  await page.goto(LOGIN_URL, { waitUntil: 'networkidle', timeout: 30000 });
  
  const captcha = await getCaptchaImage(page);
  await browser.close();
  
  return { captchaImage: captcha };
}

if (require.main === module) {
  const args = process.argv.slice(2);
  
  if (args[0] === '--captcha') {
    getCaptchaAction(args[1] || '241304104', args[2] || '')
      .then(r => console.log(JSON.stringify(r)))
      .catch(e => console.error(JSON.stringify({ error: e.message })));
  } else {
    const [u, p, captcha] = args;
    if (!u || !p) { console.error('Usage: node scraper_prod.cjs <学号> <密码> [验证码]'); process.exit(1); }
    scrapeCourses(u, p, captcha || '')
      .then(r => console.log(JSON.stringify(r)))
      .catch(e => console.error(JSON.stringify({ success: false, error: e.message })));
  }
}

module.exports = { scrapeCourses, getCaptchaImage };
