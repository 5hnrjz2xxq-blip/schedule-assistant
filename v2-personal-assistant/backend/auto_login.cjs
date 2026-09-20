const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const CAPTCHA_FILE = '/tmp/captcha_new.png';
const CODE_FILE = '/tmp/captcha_input.txt';

async function main() {
  // Clear old files
  try { fs.unlinkSync(CODE_FILE); } catch(e) {}
  try { fs.unlinkSync('/tmp/login_result.json'); } catch(e) {}

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    viewport: { width: 1920, height: 1080 }
  });
  const page = await context.newPage();

  try {
    // Go to login
    await page.goto('https://ehall.yibinu.edu.cn/authserver/login', { waitUntil: 'networkidle', timeout: 30000 });

    // Get captcha
    const captchaBase64 = await page.evaluate(() => {
      const img = document.querySelector('#captchaImg');
      if (!img || img.naturalWidth === 0) return null;
      const canvas = document.createElement('canvas');
      canvas.width = img.naturalWidth || img.width;
      canvas.height = img.naturalHeight || img.height;
      try { canvas.getContext('2d').drawImage(img, 0, 0); return canvas.toDataURL('image/png'); }
      catch (e) { return null; }
    });

    if (captchaBase64) {
      // Save captcha
      const data = captchaBase64.replace(/^data:image\/png;base64,/, '');
      fs.writeFileSync(CAPTCHA_FILE, Buffer.from(data, 'base64'));

      // Wait for code (poll every 2 seconds, up to 120 seconds)
      let code = '';
      for (let i = 0; i < 60; i++) {
        await new Promise(r => setTimeout(r, 2000));
        if (fs.existsSync(CODE_FILE)) {
          code = fs.readFileSync(CODE_FILE, 'utf-8').trim();
          if (code.length >= 4) break;
        }
      }

      if (!code) {
        fs.writeFileSync('/tmp/login_result.json', JSON.stringify({ success: false, error: '验证码等待超时' }));
        return;
      }

      // Fill credentials + captcha
      await page.fill('#username', '241304104');
      await page.fill('#password', 'Yangjiahan060428.');
      await page.waitForTimeout(300);
      await page.evaluate(() => window.encryptPassword());
      await page.waitForTimeout(300);
      await page.evaluate((c) => {
        const el = document.querySelector('#captchaResponse');
        if (el) el.value = c;
      }, code);
      await page.waitForTimeout(300);
    } else {
      // No captcha, just fill and login
      await page.fill('#username', '241304104');
      await page.fill('#password', 'Yangjiahan060428.');
      await page.waitForTimeout(300);
      await page.evaluate(() => window.encryptPassword());
      await page.waitForTimeout(300);
    }

    // Submit
    await page.evaluate(() => document.querySelector('#casLoginForm').submit());
    await page.waitForTimeout(10000);

    // Check login
    const url = page.url();
    const err = await page.evaluate(() => {
      const e = document.querySelector('.auth_error:not([style*="display: none"])');
      return e ? e.textContent.trim() : '';
    });

    if (err) {
      fs.writeFileSync('/tmp/login_result.json', JSON.stringify({ success: false, error: err }));
      return;
    }
    if (url.includes('authserver/login')) {
      fs.writeFileSync('/tmp/login_result.json', JSON.stringify({ success: false, error: '登录未生效，请重试' }));
      return;
    }

    // Navigate to schedule
    await page.goto('https://ehall.yibinu.edu.cn/new/index.html', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);
    await page.goto('https://ehall.yibinu.edu.cn/jwapp/sys/wdkb/*default/index.do#/xskcb', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(10000);

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

    // Parse courses
    function parseCell(text) {
      if (!text || text.length < 5) return null;
      const cm = text.match(/^(\w+)\s+(.+?)\s{2,}/);
      if (!cm) return null;
      const cc = cm[1];
      const nm = cm[2].match(/^(.+?)\[(\d+)\]$/);
      const cn = nm ? nm[1].trim() : cm[2].trim();
      const rest = text.substring(cm[0].length).trim();
      const parts = rest.split(/\s{2,}/);
      let teacher = '', sched = '';
      for (const p of parts) {
        if (p.includes('星期') || p.includes('周')) sched = p;
        else if (!teacher && !p.includes('节')) teacher = p.trim();
      }
      if (!sched) sched = parts[parts.length - 1] || '';
      if (!teacher && parts.length >= 2) teacher = parts[1].trim();
      let dow = 0, slot = '', loc = '', wt = '';
      const wr = [];
      if (sched) sched.split(',').forEach(seg => {
        const t = seg.trim();
        if (t.includes('星期')) dow = parseInt(t.replace('星期', '')) || 0;
        else if (t.includes('节')) slot = t.replace('节', '');
        else if (t.includes('周') && (t.includes('单') || t.includes('双'))) {
          wt = t.includes('单') ? '单' : '双';
          const m = t.match(/(\d+)-(\d+)/);
          if (m) wr.push({ start: parseInt(m[1]), end: parseInt(m[2]), type: wt });
        } else if (t.includes('周') && t.includes('-')) {
          const m = t.match(/(\d+)-(\d+)/);
          if (m) wr.push({ start: parseInt(m[1]), end: parseInt(m[2]), type: '' });
        } else if (t.includes('周')) {
          const m = t.match(/(\d+)周/);
          if (m) wr.push({ start: parseInt(m[1]), end: parseInt(m[1]), type: '' });
        } else if (t && !t.includes('节') && !t.includes('星期') && !t.includes('周')) loc = t;
      });
      let ws = 1, we = 20;
      if (wr.length > 0) { ws = Math.min(...wr.map(r => r.start)); we = Math.max(...wr.map(r => r.end)); }
      return { course_code: cc, course_name: cn, teacher, location: loc, day_of_week: dow, time_slot: slot, week_start: ws, week_end: we, week_type: wt };
    }

    const parsed = [];
    const seen = new Set();
    for (const raw of pageData.courses) {
      const p = parseCell(raw.full_text);
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

    fs.writeFileSync('/tmp/login_result.json', JSON.stringify({ success: true, courses: parsed, count: parsed.length }));
  } catch (e) {
    fs.writeFileSync('/tmp/login_result.json', JSON.stringify({ success: false, error: e.message }));
  } finally {
    await browser.close();
  }
}

main().catch(e => {
  try { fs.writeFileSync('/tmp/login_result.json', JSON.stringify({ success: false, error: e.message })); } catch(e2) {}
});
