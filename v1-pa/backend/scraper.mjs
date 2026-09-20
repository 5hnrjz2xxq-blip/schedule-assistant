/**
 * Playwright-based scraper for Yibin University (宜宾学院) course schedule
 * Uses browser automation to bypass Wisedu CAS AES encryption
 */

import { chromium } from 'playwright';

const BASE_URL = 'https://ehall.yibinu.edu.cn';
const LOGIN_URL = `${BASE_URL}/authserver/login`;
const SCHEDULE_URL = `${BASE_URL}/jwapp/sys/wdkb/*default/index.do#/xskcb`;

/**
 * Scrape course schedule from Yibin University
 * @param {string} username - Student ID
 * @param {string} password - Password
 * @returns {Promise<Array>} Array of course objects
 */
export async function scrapeCourses(username, password) {
  let browser = null;
  
  try {
    browser = await chromium.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    
    const context = await browser.newContext({
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      viewport: { width: 1920, height: 1080 }
    });
    
    const page = await context.newPage();
    
    console.log('Navigating to login page...');
    await page.goto(LOGIN_URL, { waitUntil: 'networkidle' });
    
    console.log('Filling in credentials...');
    await page.fill('#username', username);
    await page.fill('#password', password);
    
    console.log('Submitting login form...');
    await page.click('button.auth_login_btn[type="submit"]');
    
    console.log('Waiting for login to complete...');
    await page.waitForURL('**/authserver/login?service=*', { 
      timeout: 30000,
      waitUntil: 'networkidle'
    }).catch(() => {});
    
    await page.waitForTimeout(3000);
    
    const currentUrl = page.url();
    if (currentUrl.includes('authserver/login')) {
      throw new Error('Login failed - still on login page');
    }
    
    console.log('Login successful');
    
    console.log('Attempting direct API call for course data...');
    const apiCourses = await page.evaluate(async () => {
      try {
        const response = await fetch('/jwapp/sys/wdkb/api/xskcb/xskcbList.do', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: 'XNXQDM=&SKZC=1'
        });
        if (response.ok) return await response.json();
      } catch (e) {}
      return null;
    });
    
    if (apiCourses && apiCourses.data && apiCourses.data.length > 0) {
      console.log(`Got ${apiCourses.data.length} courses from API`);
      const courses = processApiData([apiCourses]);
      await browser.close();
      return courses;
    }
    
    console.log('Navigating to schedule page...');
    await page.goto(SCHEDULE_URL, { waitUntil: 'networkidle' });
    
    console.log('Waiting for schedule data to load...');
    await page.waitForTimeout(5000);
    
    try {
      await page.waitForSelector('table tbody tr, .schedule-item, .course-item', { timeout: 15000 });
    } catch (e) {}
    
    console.log('Extracting course data...');
    const courses = await page.evaluate(() => {
      const courses = [];
      
      const tableRows = document.querySelectorAll('table tbody tr');
      if (tableRows.length > 0) {
        tableRows.forEach(row => {
          const cells = row.querySelectorAll('td');
          if (cells.length >= 5) {
            courses.push({
              course_name: cells[0]?.textContent?.trim() || '',
              teacher: cells[1]?.textContent?.trim() || '',
              location: cells[2]?.textContent?.trim() || '',
              day_of_week: parseInt(cells[3]?.textContent?.trim()) || 0,
              time_slot: cells[4]?.textContent?.trim() || '',
              week_start: parseInt(cells[5]?.textContent?.trim()) || 0,
              week_end: parseInt(cells[6]?.textContent?.trim()) || 0,
              week_type: cells[7]?.textContent?.trim() || '',
              course_code: cells[8]?.textContent?.trim() || ''
            });
          }
        });
      }
      
      if (courses.length === 0) {
        const scheduleItems = document.querySelectorAll('.xskcb-table .row, .course-row, [class*="schedule"]');
        scheduleItems.forEach(item => {
          const nameEl = item.querySelector('.course-name, .kcmc, [data-field="KCMC"]');
          if (nameEl) {
            courses.push({
              course_name: nameEl?.textContent?.trim() || '',
              teacher: item.querySelector('.teacher, .jsxm, [data-field="JSXM"]')?.textContent?.trim() || '',
              location: item.querySelector('.location, .jsmc, [data-field="JSMC"]')?.textContent?.trim() || '',
              day_of_week: 0, time_slot: '', week_start: 0, week_end: 0, week_type: '', course_code: ''
            });
          }
        });
      }
      
      return courses;
    });
    
    if (courses.length === 0) {
      console.log('DOM extraction failed, attempting network interception...');
      const apiData = [];
      
      page.on('response', async (response) => {
        const url = response.url();
        if (url.includes('xskcb') || url.includes('schedule') || url.includes('course') || url.includes('kbxx')) {
          try {
            const ct = response.headers()['content-type'] || '';
            if (ct.includes('json')) {
              apiData.push(await response.json());
            }
          } catch (e) {}
        }
      });
      
      await page.reload({ waitUntil: 'networkidle' });
      await page.waitForTimeout(8000);
      
      if (apiData.length > 0) {
        courses.push(...processApiData(apiData));
      }
    }
    
    console.log(`Extracted ${courses.length} courses`);
    return courses;
    
  } catch (error) {
    console.error('Scraping error:', error.message);
    throw error;
  } finally {
    if (browser) await browser.close();
  }
}

function processApiData(apiData) {
  const courses = [];
  for (const data of apiData) {
    const items = data?.data || data?.rows || data?.list || [];
    for (const item of items) {
      courses.push({
        course_name: item.KCMC || item.courseName || item.name || '',
        teacher: item.JSXM || item.teacher || item.teacherName || '',
        location: item.JSMC || item.location || item.classroom || '',
        day_of_week: parseInt(item.XQ || item.dayOfWeek || item.weekday) || 0,
        time_slot: item.KSJC && item.JSJC ? `${item.KSJC}-${item.JSJC}` : (item.timeSlot || ''),
        week_start: parseInt(item.KSZC || item.weekStart) || 0,
        week_end: parseInt(item.JSZC || item.weekEnd) || 0,
        week_type: item.ZC || item.weekType || '',
        course_code: item.KCDM || item.courseCode || item.code || ''
      });
    }
  }
  return courses;
}

if (process.argv[1] === import.meta.url) {
  const username = process.argv[2];
  const password = process.argv[3];
  if (!username || !password) {
    console.error('Usage: node scraper.mjs <username> <password>');
    process.exit(1);
  }
  scrapeCourses(username, password)
    .then(courses => console.log('Courses:', JSON.stringify(courses, null, 2)))
    .catch(error => { console.error('Error:', error); process.exit(1); });
}
