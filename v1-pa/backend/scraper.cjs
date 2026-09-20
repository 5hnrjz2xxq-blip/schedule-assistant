/**
 * Playwright-based scraper for Yibin University (宜宾学院) course schedule
 * Uses browser automation to bypass Wisedu CAS AES encryption
 * CommonJS format (.cjs) to avoid macOS file locking issues with .mjs
 */

const { chromium } = require('playwright');

const BASE_URL = 'https://ehall.yibinu.edu.cn';
const LOGIN_URL = `${BASE_URL}/authserver/login`;
const SCHEDULE_URL = `${BASE_URL}/jwapp/sys/wdkb/*default/index.do#/xskcb`;

/**
 * Scrape course schedule from Yibin University
 * @param {string} username - Student ID
 * @param {string} password - Password
 * @returns {Promise<Array>} Array of course objects
 */
async function scrapeCourses(username, password) {
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

    // Collect API responses for course data
    const apiData = [];
    page.on('response', async (response) => {
      const url = response.url();
      if (url.includes('xskcb') || url.includes('kbxx') || url.includes('schedule') || url.includes('course')) {
        try {
          const ct = response.headers()['content-type'] || '';
          if (ct.includes('json')) {
            const json = await response.json();
            apiData.push(json);
          }
        } catch (e) {
          // response body may not be available
        }
      }
    });

    console.log('Navigating to login page...');
    await page.goto(LOGIN_URL, { waitUntil: 'networkidle', timeout: 30000 });

    console.log('Filling in credentials...');
    await page.fill('#username', username);
    await page.fill('#password', password);

    console.log('Submitting login form...');
    await page.click('button.auth_login_btn[type="submit"]');

    // Wait for navigation away from login page (CAS redirects through several URLs)
    console.log('Waiting for login to complete...');
    try {
      await page.waitForURL((url) => !url.includes('authserver/login') && url !== LOGIN_URL, {
        timeout: 20000
      });
    } catch (e) {
      // If we're still on login page, check for error message
      const errorText = await page.$eval('.auth_error, .error-msg, #errorMsg', el => el.textContent.trim()).catch(() => null);
      if (errorText) {
        throw new Error(`Login failed: ${errorText}`);
      }
    }

    // Give the page time to settle after CAS redirect
    await page.waitForTimeout(2000);

    const currentUrl = page.url();
    console.log(`Current URL after login: ${currentUrl}`);
    if (currentUrl.includes('authserver/login') && !currentUrl.includes('service=')) {
      throw new Error('Login failed - still on login page');
    }

    console.log('Login successful');

    // Try direct API call first (most reliable)
    console.log('Attempting direct API call for course data...');
    const apiCourses = await page.evaluate(async () => {
      try {
        const response = await fetch('/jwapp/sys/wdkb/api/xskcb/xskcbList.do', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: 'XNXQDM=&SKZC=1'
        });
        if (response.ok) return await response.json();
      } catch (e) {
        console.error('API call failed:', e);
      }
      return null;
    });

    if (apiCourses && apiCourses.data && apiCourses.data.length > 0) {
      console.log(`Got ${apiCourses.data.length} courses from API`);
      const courses = processApiData([apiCourses]);
      await browser.close();
      return courses;
    }

    // Fallback: navigate to schedule page and intercept network requests
    console.log('Direct API failed, navigating to schedule page...');
    await page.goto(SCHEDULE_URL, { waitUntil: 'networkidle', timeout: 30000 });

    console.log('Waiting for schedule data to load...');
    await page.waitForTimeout(5000);

    // Try to wait for table content
    try {
      await page.waitForSelector('table tbody tr, .schedule-item, .course-item', { timeout: 15000 });
    } catch (e) {
      // No table found, try other methods
    }

    // Try DOM extraction
    console.log('Extracting course data from DOM...');
    const domCourses = await page.evaluate(() => {
      const courses = [];

      // Method 1: Table rows
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

      // Method 2: Vue/React component data
      if (courses.length === 0) {
        const items = document.querySelectorAll('[class*="course"], [class*="schedule"], [class*="kcmc"]');
        items.forEach(item => {
          const name = item.querySelector('.course-name, .kcmc, [data-field="KCMC"], td:first-child');
          if (name && name.textContent.trim()) {
            courses.push({
              course_name: name.textContent.trim(),
              teacher: item.querySelector('.teacher, .jsxm, [data-field="JSXM"]')?.textContent?.trim() || '',
              location: item.querySelector('.location, .jsmc, [data-field="JSMC"]')?.textContent?.trim() || '',
              day_of_week: 0, time_slot: '', week_start: 0, week_end: 0, week_type: '', course_code: ''
            });
          }
        });
      }

      return courses;
    });

    if (domCourses.length > 0) {
      console.log(`Got ${domCourses.length} courses from DOM`);
      await browser.close();
      return domCourses;
    }

    // Final fallback: check intercepted network responses
    if (apiData.length > 0) {
      console.log(`Got ${apiData.length} API responses from network interception`);
      const courses = processApiData(apiData);
      await browser.close();
      return courses;
    }

    console.log('No courses found via any method');
    return [];

  } catch (error) {
    console.error('Scraping error:', error.message);
    throw error;
  } finally {
    if (browser) await browser.close();
  }
}

/**
 * Process raw API response data into normalized course objects
 */
function processApiData(apiData) {
  const courses = [];
  for (const data of apiData) {
    // Wisedu APIs return data in different structures
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

// Run directly from command line
if (require.main === module) {
  const username = process.argv[2];
  const password = process.argv[3];
  if (!username || !password) {
    console.error('Usage: node scraper.cjs <username> <password>');
    process.exit(1);
  }
  scrapeCourses(username, password)
    .then(courses => console.log(JSON.stringify(courses, null, 2)))
    .catch(error => {
      console.error('Error:', error.message);
      process.exit(1);
    });
}

module.exports = { scrapeCourses };
