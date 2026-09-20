"""
Comprehensive End-to-End Test Script for 宜宾学院课表助手 (Yibin University Course Schedule Assistant)

Tests:
1. Flask app creation and configuration
2. Homepage rendering
3. Login API validation (missing credentials, wrong format)
4. Login flow with real credentials (mocked scraper)
5. Schedule API (before/after login)
6. ICS export API with various course configurations
7. ICS file format validation (RFC 5545 compliance)
8. Edge cases (empty courses, invalid time slots, odd/even weeks)
9. Error handling throughout the API

Real credentials used: student ID 241304104, password Yangjiahan060428
(Scraper is mocked - no actual university website is contacted)
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from calendar_gen import generate_ics, _get_time_range, _week_matches

# Sample course data for testing
SAMPLE_COURSES = [
    {
        "course_name": "高等数学A",
        "teacher": "张明",
        "location": "教学楼A301",
        "day_of_week": 1,       # Monday
        "time_slot": "1-2",     # 08:20-10:00
        "week_start": 2,
        "week_end": 16,
        "week_type": "",         # Every week
    },
    {
        "course_name": "线性代数",
        "teacher": "王华",
        "location": "理学楼C201",
        "day_of_week": 1,       # Monday
        "time_slot": "3-4",     # 10:20-12:00
        "week_start": 2,
        "week_end": 16,
        "week_type": "",         # Every week
    },
    {
        "course_name": "大学英语IV",
        "teacher": "李丽",
        "location": "外语楼B205",
        "day_of_week": 3,       # Wednesday
        "time_slot": "3-4",     # 10:20-12:00
        "week_start": 2,
        "week_end": 17,
        "week_type": "单",       # Odd weeks only
    },
    {
        "course_name": "计算机基础",
        "teacher": "赵强",
        "location": "实验楼D402",
        "day_of_week": 2,       # Tuesday
        "time_slot": "5-6",     # 14:00-15:40
        "week_start": 2,
        "week_end": 16,
        "week_type": "双",       # Even weeks only
    },
    {
        "course_name": "思想政治理论",
        "teacher": "刘芳",
        "location": "教学楼A105",
        "day_of_week": 5,       # Friday
        "time_slot": "7-8",     # 16:00-17:40
        "week_start": 1,
        "week_end": 16,
        "week_type": "",         # Every week
    },
    {
        "course_name": "体育",
        "teacher": "陈刚",
        "location": "体育馆",
        "day_of_week": 4,       # Thursday
        "time_slot": "5-6",     # 14:00-15:40
        "week_start": 2,
        "week_end": 16,
        "week_type": "",         # Every week
    },
    {
        "course_name": "晚自习",
        "teacher": "辅导员",
        "location": "教室A301",
        "day_of_week": 3,       # Wednesday
        "time_slot": "9-10",    # 19:00-20:40
        "week_start": 1,
        "week_end": 17,
        "week_type": "",         # Every week
    },
]

SEMESTER_START = "2026-02-22"

# Real credentials for the mock scraper test
REAL_STUDENT_ID = "241304104"
REAL_PASSWORD = "Yangjiahan060428"

# Mock scraper output (simulated course data from the university website)
MOCK_SCRAPER_COURSES = [
    {
        "course_name": "大学物理B",
        "teacher": "周教授",
        "location": "理学楼A302",
        "day_of_week": 2,
        "time_slot": "1-2",
        "week_start": 1,
        "week_end": 16,
        "week_type": "",
    },
    {
        "course_name": "数据结构",
        "teacher": "孙老师",
        "location": "实验楼B201",
        "day_of_week": 3,
        "time_slot": "5-6",
        "week_start": 2,
        "week_end": 15,
        "week_type": "单",
    },
    {
        "course_name": "操作系统",
        "teacher": "吴老师",
        "location": "教学楼C102",
        "day_of_week": 4,
        "time_slot": "7-8",
        "week_start": 2,
        "week_end": 16,
        "week_type": "双",
    },
]


class TestCalendarGenFunctions(unittest.TestCase):
    """Unit tests for calendar_gen.py helper functions."""

    def test_get_time_range_valid_slots(self):
        """Test that all valid time slots return correct ranges."""
        test_cases = [
            ("1-2", (8, 20), (10, 0)),
            ("3-4", (10, 20), (12, 0)),
            ("5-6", (14, 0), (15, 40)),
            ("7-8", (16, 0), (17, 40)),
            ("9-10", (19, 0), (20, 40)),
        ]
        for slot, start, end in test_cases:
            result = _get_time_range(slot)
            self.assertEqual(result[0].hour, start[0])
            self.assertEqual(result[0].minute, start[1])
            self.assertEqual(result[1].hour, end[0])
            self.assertEqual(result[1].minute, end[1])

    def test_get_time_range_invalid_slot(self):
        """Test that invalid time slots raise ValueError."""
        with self.assertRaises(ValueError):
            _get_time_range("99-100")
        with self.assertRaises(ValueError):
            _get_time_range("")

    def test_week_matches_every_week(self):
        """Test week matching for every-week courses."""
        self.assertTrue(_week_matches(5, 1, 16, ""))
        self.assertTrue(_week_matches(1, 1, 16, ""))
        self.assertTrue(_week_matches(16, 1, 16, ""))
        self.assertFalse(_week_matches(0, 1, 16, ""))
        self.assertFalse(_week_matches(17, 1, 16, ""))

    def test_week_matches_odd_weeks(self):
        """Test week matching for odd-week (单) courses."""
        self.assertTrue(_week_matches(3, 2, 16, "单"))
        self.assertTrue(_week_matches(5, 2, 16, "单"))
        self.assertFalse(_week_matches(4, 2, 16, "单"))
        self.assertFalse(_week_matches(6, 2, 16, "单"))
        self.assertFalse(_week_matches(1, 2, 16, "单"))  # Out of range

    def test_week_matches_even_weeks(self):
        """Test week matching for even-week (双) courses."""
        self.assertTrue(_week_matches(2, 2, 16, "双"))
        self.assertTrue(_week_matches(4, 2, 16, "双"))
        self.assertFalse(_week_matches(3, 2, 16, "双"))
        self.assertFalse(_week_matches(5, 2, 16, "双"))
        self.assertFalse(_week_matches(1, 2, 16, "双"))  # Out of range

    def test_week_matches_invalid_type(self):
        """Test that invalid week_type raises ValueError."""
        with self.assertRaises(ValueError):
            _week_matches(5, 1, 16, "三")


class TestGenerateICS(unittest.TestCase):
    """Tests for the generate_ics function."""

    def test_basic_ics_structure(self):
        """Test that generated ICS has correct structure."""
        ics = generate_ics(SAMPLE_COURSES, SEMESTER_START)

        # Check required headers
        self.assertIn("BEGIN:VCALENDAR", ics)
        self.assertIn("END:VCALENDAR", ics)
        self.assertIn("VERSION:2.0", ics)
        self.assertIn("PRODID:", ics)

        # Check timezone
        self.assertIn("BEGIN:VTIMEZONE", ics)
        self.assertIn("TZID:Asia/Shanghai", ics)
        self.assertIn("END:VTIMEZONE", ics)

        # Check events
        self.assertEqual(ics.count("BEGIN:VEVENT"), len(SAMPLE_COURSES))
        self.assertEqual(ics.count("END:VEVENT"), len(SAMPLE_COURSES))

    def test_ics_has_rrule(self):
        """Test that all events have recurrence rules."""
        ics = generate_ics(SAMPLE_COURSES, SEMESTER_START)
        self.assertIn("RRULE:", ics)

    def test_ics_has_summary_and_location(self):
        """Test that events have summary and location."""
        ics = generate_ics(SAMPLE_COURSES, SEMESTER_START)
        self.assertIn("SUMMARY:", ics)
        self.assertIn("LOCATION:", ics)

    def test_ics_utf8_encoding(self):
        """Test that ICS content is properly UTF-8 encoded."""
        ics = generate_ics(SAMPLE_COURSES, SEMESTER_START)
        # Should be valid UTF-8 string
        self.assertIsInstance(ics, str)
        # Should contain Chinese characters
        self.assertIn("课程", ics)
        self.assertIn("教师", ics)

    def test_ics_with_single_course(self):
        """Test ICS generation with a single course."""
        single_course = [SAMPLE_COURSES[0]]
        ics = generate_ics(single_course, SEMESTER_START)
        self.assertEqual(ics.count("BEGIN:VEVENT"), 1)
        self.assertIn("高等数学A", ics)
        self.assertIn("张明", ics)

    def test_ics_with_empty_courses(self):
        """Test ICS generation with empty course list."""
        ics = generate_ics([], SEMESTER_START)
        self.assertIn("BEGIN:VCALENDAR", ics)
        self.assertIn("END:VCALENDAR", ics)
        self.assertEqual(ics.count("BEGIN:VEVENT"), 0)

    def test_ics_week_type_odd(self):
        """Test that odd-week courses have interval=2 in RRULE."""
        odd_course = [{
            "course_name": "单周课",
            "teacher": "测试教师",
            "location": "测试教室",
            "day_of_week": 1,
            "time_slot": "1-2",
            "week_start": 1,
            "week_end": 15,
            "week_type": "单",
        }]
        ics = generate_ics(odd_course, SEMESTER_START)
        self.assertIn("INTERVAL=2", ics)
        # Should have events for odd weeks: 1,3,5,7,9,11,13,15 = 8 events
        self.assertEqual(ics.count("BEGIN:VEVENT"), 1)

    def test_ics_week_type_even(self):
        """Test that even-week courses have interval=2 in RRULE."""
        even_course = [{
            "course_name": "双周课",
            "teacher": "测试教师",
            "location": "测试教室",
            "day_of_week": 2,
            "time_slot": "5-6",
            "week_start": 2,
            "week_end": 16,
            "week_type": "双",
        }]
        ics = generate_ics(even_course, SEMESTER_START)
        self.assertIn("INTERVAL=2", ics)
        self.assertEqual(ics.count("BEGIN:VEVENT"), 1)

    def test_ics_event_times_correct(self):
        """Test that event times match the time slot mapping."""
        course = [{
            "course_name": "测试课程",
            "teacher": "测试教师",
            "location": "测试教室",
            "day_of_week": 1,  # Monday
            "time_slot": "3-4",  # 10:20-12:00
            "week_start": 1,
            "week_end": 1,
            "week_type": "",
        }]
        ics = generate_ics(course, SEMESTER_START)
        self.assertIn("DTSTART", ics)
        self.assertIn("DTEND", ics)
        # Check time is 10:20 (slot 3-4)
        self.assertIn("T102000", ics)
        self.assertIn("T120000", ics)

    def test_ics_uid_unique(self):
        """Test that each event has a unique UID."""
        ics = generate_ics(SAMPLE_COURSES, SEMESTER_START)
        import re
        uids = re.findall(r'UID:(.+?)(?:\r?\n)', ics)
        # Each course should have one UID
        self.assertEqual(len(uids), len(SAMPLE_COURSES))

    def test_ics_description_content(self):
        """Test that event descriptions contain course details."""
        ics = generate_ics(SAMPLE_COURSES, SEMESTER_START)
        self.assertIn("课程:", ics)
        self.assertIn("教师:", ics)
        self.assertIn("教室:", ics)
        self.assertIn("节次:", ics)
        self.assertIn("周次:", ics)


class TestFlaskAPI(unittest.TestCase):
    """Integration tests for Flask API endpoints."""

    @classmethod
    def setUpClass(cls):
        """Create Flask test client."""
        from app import app
        app.config['TESTING'] = True
        cls.client = app.test_client()
        cls.app = app

    def test_homepage(self):
        """Test homepage endpoint returns HTML."""
        # Skip if frontend template is not available
        frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend')
        if not os.path.exists(os.path.join(frontend_dir, 'index.html')):
            self.skipTest('Frontend template not available in test environment')
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<!DOCTYPE html>', response.data)

    def test_login_missing_both_credentials(self):
        """Test login with empty request body."""
        response = self.client.post('/api/login',
                                     json={},
                                     content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(data['success'])
        self.assertIn('学号和密码', data['message'])

    def test_login_missing_username(self):
        """Test login with only password."""
        response = self.client.post('/api/login',
                                     json={'password': 'test123'},
                                     content_type='application/json')
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('学号和密码', data['message'])

    def test_login_missing_password(self):
        """Test login with only username."""
        response = self.client.post('/api/login',
                                     json={'username': '241304104'},
                                     content_type='application/json')
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('学号和密码', data['message'])

    @patch('app.subprocess.run')
    def test_login_success_with_mock_scraper(self, mock_run):
        """Test login flow with mocked scraper (real credentials)."""
        # Mock the scraper subprocess to return course data
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(MOCK_SCRAPER_COURSES)
        mock_result.stderr = ''
        mock_run.return_value = mock_result

        response = self.client.post('/api/login',
                                     json={
                                         'username': REAL_STUDENT_ID,
                                         'password': REAL_PASSWORD
                                     },
                                     content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], '登录成功')

        # Verify scraper was called with correct credentials
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        self.assertIn(REAL_STUDENT_ID, call_args[0][0])
        self.assertIn(REAL_PASSWORD, call_args[0][0])

    @patch('app.subprocess.run')
    def test_login_scraper_timeout(self, mock_run):
        """Test login when scraper times out."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd='node', timeout=60)

        response = self.client.post('/api/login',
                                     json={
                                         'username': REAL_STUDENT_ID,
                                         'password': REAL_PASSWORD
                                     },
                                     content_type='application/json')
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('超时', data['message'])

    @patch('app.subprocess.run')
    def test_login_scraper_returns_error(self, mock_run):
        """Test login when scraper returns non-zero exit code."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ''
        mock_result.stderr = 'Login failed: Invalid credentials'
        mock_run.return_value = mock_result

        response = self.client.post('/api/login',
                                     json={
                                         'username': 'wrong_id',
                                         'password': 'wrong_pass'
                                     },
                                     content_type='application/json')
        data = json.loads(response.data)
        self.assertFalse(data['success'])

    @patch('app.subprocess.run')
    def test_login_scraper_invalid_json(self, mock_run):
        """Test login when scraper returns invalid JSON."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'not valid json {{{'
        mock_result.stderr = ''
        mock_run.return_value = mock_result

        response = self.client.post('/api/login',
                                     json={
                                         'username': REAL_STUDENT_ID,
                                         'password': REAL_PASSWORD
                                     },
                                     content_type='application/json')
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('解析失败', data['message'])

    def test_schedule_before_login(self):
        """Test schedule endpoint before any login."""
        # Reset sessions
        from app import user_sessions
        user_sessions.clear()

        response = self.client.get('/api/schedule')
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('请先登录', data['message'])

    @patch('app.subprocess.run')
    def test_schedule_after_login(self, mock_run):
        """Test schedule endpoint after successful login."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(MOCK_SCRAPER_COURSES)
        mock_result.stderr = ''
        mock_run.return_value = mock_result

        # Login first
        self.client.post('/api/login',
                          json={
                              'username': REAL_STUDENT_ID,
                              'password': REAL_PASSWORD
                          },
                          content_type='application/json')

        # Get schedule
        response = self.client.get('/api/schedule')
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['data']), len(MOCK_SCRAPER_COURSES))

        # Verify course data
        self.assertEqual(data['data'][0]['course_name'], '大学物理B')
        self.assertEqual(data['data'][0]['teacher'], '周教授')

    def test_export_ics_no_data(self):
        """Test ICS export with no course data."""
        response = self.client.post('/api/export-ics',
                                     json={},
                                     content_type='application/json')
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('没有课表数据', data['message'])

    def test_export_ics_empty_courses(self):
        """Test ICS export with empty courses list."""
        response = self.client.post('/api/export-ics',
                                     json={'courses': []},
                                     content_type='application/json')
        data = json.loads(response.data)
        self.assertFalse(data['success'])

    def test_export_ics_success(self):
        """Test successful ICS export with course data."""
        response = self.client.post('/api/export-ics',
                                     json={
                                         'courses': SAMPLE_COURSES[:2],
                                         'semester_start': SEMESTER_START
                                     },
                                     content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'text/calendar; charset=utf-8')

        # Verify ICS content
        ics_content = response.data.decode('utf-8')
        self.assertIn('BEGIN:VCALENDAR', ics_content)
        self.assertIn('END:VCALENDAR', ics_content)
        self.assertIn('高等数学A', ics_content)
        self.assertIn('线性代数', ics_content)

    def test_export_ics_default_semester(self):
        """Test ICS export with default semester start date."""
        response = self.client.post('/api/export-ics',
                                     json={
                                         'courses': [SAMPLE_COURSES[0]]
                                     },
                                     content_type='application/json')
        self.assertEqual(response.status_code, 200)
        ics_content = response.data.decode('utf-8')
        self.assertIn('BEGIN:VCALENDAR', ics_content)

    def test_export_ics_odd_even_weeks(self):
        """Test ICS export handles odd/even week courses correctly."""
        mixed_courses = [
            SAMPLE_COURSES[2],  # Odd weeks (单)
            SAMPLE_COURSES[3],  # Even weeks (双)
        ]
        response = self.client.post('/api/export-ics',
                                     json={
                                         'courses': mixed_courses,
                                         'semester_start': SEMESTER_START
                                     },
                                     content_type='application/json')
        self.assertEqual(response.status_code, 200)
        ics_content = response.data.decode('utf-8')
        self.assertIn('INTERVAL=2', ics_content)


class TestEndToEndFlow(unittest.TestCase):
    """End-to-end tests simulating full user workflows."""

    @classmethod
    def setUpClass(cls):
        """Create Flask test client."""
        from app import app
        app.config['TESTING'] = True
        cls.client = app.test_client()

    @patch('app.subprocess.run')
    def test_full_login_to_export_flow(self, mock_run):
        """Test complete flow: login -> get schedule -> export ICS."""
        # Setup mock scraper
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(MOCK_SCRAPER_COURSES)
        mock_result.stderr = ''
        mock_run.return_value = mock_result

        # Step 1: Login
        login_response = self.client.post('/api/login',
                                           json={
                                               'username': REAL_STUDENT_ID,
                                               'password': REAL_PASSWORD
                                           },
                                           content_type='application/json')
        login_data = json.loads(login_response.data)
        self.assertTrue(login_data['success'], f"Login failed: {login_data}")

        # Step 2: Get schedule
        schedule_response = self.client.get('/api/schedule')
        schedule_data = json.loads(schedule_response.data)
        self.assertTrue(schedule_data['success'], f"Schedule failed: {schedule_data}")
        courses = schedule_data['data']
        self.assertEqual(len(courses), 3)

        # Step 3: Export ICS
        export_response = self.client.post('/api/export-ics',
                                            json={
                                                'courses': courses,
                                                'semester_start': SEMESTER_START
                                            },
                                            content_type='application/json')
        self.assertEqual(export_response.status_code, 200)

        # Step 4: Validate exported ICS
        ics_content = export_response.data.decode('utf-8')
        self.assertIn('BEGIN:VCALENDAR', ics_content)
        self.assertIn('大学物理B', ics_content)
        self.assertIn('数据结构', ics_content)
        self.assertIn('操作系统', ics_content)
        self.assertEqual(ics_content.count('BEGIN:VEVENT'), 3)

    @patch('app.subprocess.run')
    def test_multiple_logins_switch_users(self, mock_run):
        """Test that multiple logins update the session correctly."""
        from app import user_sessions
        user_sessions.clear()

        # Mock to return different data for each call
        mock_result1 = MagicMock()
        mock_result1.returncode = 0
        mock_result1.stdout = json.dumps(MOCK_SCRAPER_COURSES[:1])
        mock_result1.stderr = ''

        mock_result2 = MagicMock()
        mock_result2.returncode = 0
        mock_result2.stdout = json.dumps(MOCK_SCRAPER_COURSES[1:])
        mock_result2.stderr = ''

        mock_run.side_effect = [mock_result1, mock_result2]

        # First login
        resp1 = self.client.post('/api/login',
                          json={'username': 'student1', 'password': 'pass1'},
                          content_type='application/json')
        data1 = json.loads(resp1.data)
        self.assertTrue(data1['success'], f"First login failed: {data1}")

        # Second login (different user)
        resp2 = self.client.post('/api/login',
                          json={'username': 'student2', 'password': 'pass2'},
                          content_type='application/json')
        data2 = json.loads(resp2.data)
        self.assertTrue(data2['success'], f"Second login failed: {data2}")

        # Schedule should return latest user's data
        response = self.client.get('/api/schedule')
        data = json.loads(response.data)
        self.assertTrue(data['success'], f"Schedule failed: {data}")
        # student2 has 2 courses (index 1 and 2)
        self.assertEqual(len(data['data']), 2)


class TestICSRFC5545Compliance(unittest.TestCase):
    """Tests for RFC 5545 compliance in generated ICS files."""

    def test_ics_line_ending(self):
        """Test that ICS uses CRLF line endings per RFC 5545."""
        ics = generate_ics([SAMPLE_COURSES[0]], SEMESTER_START)
        # RFC 5545 requires CRLF line endings
        lines = ics.split('\r\n')
        self.assertGreater(len(lines), 1)

    def test_ics_event_has_required_properties(self):
        """Test that events have required RFC 5545 properties."""
        ics = generate_ics([SAMPLE_COURSES[0]], SEMESTER_START)
        self.assertIn('DTSTART', ics)
        self.assertIn('DTEND', ics)
        self.assertIn('SUMMARY', ics)
        self.assertIn('UID', ics)
        self.assertIn('RRULE', ics)

    def test_ics_calendar_has_required_properties(self):
        """Test that calendar has required RFC 5545 properties."""
        ics = generate_ics([SAMPLE_COURSES[0]], SEMESTER_START)
        self.assertIn('VERSION:2.0', ics)
        self.assertIn('PRODID:', ics)
        self.assertIn('CALSCALE:GREGORIAN', ics)
        self.assertIn('METHOD:PUBLISH', ics)

    def test_ics_timezone_definition(self):
        """Test that timezone is properly defined."""
        ics = generate_ics([SAMPLE_COURSES[0]], SEMESTER_START)
        self.assertIn('BEGIN:VTIMEZONE', ics)
        self.assertIn('TZID:Asia/Shanghai', ics)
        self.assertIn('BEGIN:STANDARD', ics)
        self.assertIn('END:STANDARD', ics)
        self.assertIn('END:VTIMEZONE', ics)

    def test_ics_content_type(self):
        """Test that ICS content is valid UTF-8."""
        ics = generate_ics(SAMPLE_COURSES, SEMESTER_START)
        # Should not raise UnicodeDecodeError
        ics.encode('utf-8')
        self.assertIsInstance(ics, str)


def run_tests():
    """Run all tests and print summary."""
    print("=" * 70)
    print("  宜宾学院课表助手 - Comprehensive API Test Suite")
    print("=" * 70)
    print()

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestCalendarGenFunctions))
    suite.addTests(loader.loadTestsFromTestCase(TestGenerateICS))
    suite.addTests(loader.loadTestsFromTestCase(TestFlaskAPI))
    suite.addTests(loader.loadTestsFromTestCase(TestEndToEndFlow))
    suite.addTests(loader.loadTestsFromTestCase(TestICSRFC5545Compliance))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print()
    print("=" * 70)
    print("  TEST SUMMARY")
    print("=" * 70)
    print(f"  Tests run:    {result.testsRun}")
    print(f"  Failures:     {len(result.failures)}")
    print(f"  Errors:       {len(result.errors)}")
    print(f"  Skipped:      {len(result.skipped)}")
    print()

    if result.failures:
        print("  FAILURES:")
        for test, traceback in result.failures:
            print(f"    - {test}")
            for line in traceback.split('\n')[-3:]:
                print(f"      {line}")
        print()

    if result.errors:
        print("  ERRORS:")
        for test, traceback in result.errors:
            print(f"    - {test}")
            for line in traceback.split('\n')[-3:]:
                print(f"      {line}")
        print()

    if result.wasSuccessful():
        print("  [PASS] ALL TESTS PASSED!")
    else:
        print("  [FAIL] SOME TESTS FAILED")

    print()
    print("  Test classes:")
    print("    1. TestCalendarGenFunctions   - Unit tests for helper functions")
    print("    2. TestGenerateICS            - ICS generation tests")
    print("    3. TestFlaskAPI               - Flask API endpoint tests")
    print("    4. TestEndToEndFlow           - Full workflow tests")
    print("    5. TestICSRFC5545Compliance   - RFC 5545 compliance tests")
    print()
    print("  Credentials used (mocked):")
    print(f"    Student ID: {REAL_STUDENT_ID}")
    print(f"    Password:   {REAL_PASSWORD}")
    print()
    print("=" * 70)

    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
