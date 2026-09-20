"""
Test file for the calendar generator module.

Generates a sample .ics file with realistic course schedule data
from 宜宾学院 (Yibin University) and saves it to test.ics.
"""

import os
import sys
from calendar_gen import generate_ics

# Sample course schedule data for Yibin University
sample_courses = [
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

# Semester start date (Monday of week 1)
SEMESTER_START = "2026-02-22"


def main():
    print("=" * 60)
    print("  宜宾学院 课程表 .ics 文件生成测试")
    print("=" * 60)
    print()

    # Generate the .ics content
    ics_content = generate_ics(sample_courses, SEMESTER_START)

    # Save to file
    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, "test.ics")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ics_content)

    print(f"[OK] Generated .ics file: {output_path}")
    print(f"[OK] File size: {len(ics_content)} bytes")
    print()

    # Count expected events
    expected_events = 0
    for course in sample_courses:
        week_start = course["week_start"]
        week_end = course["week_end"]
        week_type = course.get("week_type", "")
        for week in range(week_start, week_end + 1):
            if week_type == "":
                expected_events += 1
            elif week_type == "单" and week % 2 == 1:
                expected_events += 1
            elif week_type == "双" and week % 2 == 0:
                expected_events += 1

    print(f"[INFO] Courses: {len(sample_courses)}")
    print(f"[INFO] Expected events: {expected_events}")
    print(f"[INFO] Semester: {SEMESTER_START} (Spring 2026)")
    print()

    # Verify basic .ics structure
    checks = [
        ("BEGIN:VCALENDAR" in ics_content, "VCALENDAR header present"),
        ("END:VCALENDAR" in ics_content, "VCALENDAR footer present"),
        ("VERSION:2.0" in ics_content, "Version 2.0 present"),
        ("PRODID:" in ics_content, "PRODID present"),
        ("BEGIN:VTIMEZONE" in ics_content, "VTIMEZONE present"),
        ("TZID:Asia/Shanghai" in ics_content, "Asia/Shanghai timezone present"),
        (ics_content.count("BEGIN:VEVENT") == len(sample_courses), f"Correct event count ({len(sample_courses)})"),
        ("RRULE:" in ics_content, "RRULE present"),
        ("SUMMARY:" in ics_content, "SUMMARY present"),
        ("LOCATION:" in ics_content, "LOCATION present"),
    ]

    print("Validation checks:")
    all_passed = True
    for check, label in checks:
        status = "PASS" if check else "FAIL"
        if not check:
            all_passed = False
        print(f"  [{status}] {label}")
    print()

    if all_passed:
        print("[OK] All validation checks passed!")
    else:
        print("[WARN] Some checks failed - review the output.")

    print()
    print("To import into Apple Calendar:")
    print("  1. Transfer test.ics to your Mac/iPhone")
    print("  2. Double-click the file, or")
    print("  3. In Apple Calendar: File > Import > Select test.ics")
    print()

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
