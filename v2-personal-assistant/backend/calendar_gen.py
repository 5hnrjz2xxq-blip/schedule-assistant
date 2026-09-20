"""
iCalendar (.ics) file generator for Chinese university course schedules.

Generates RFC 5545 compliant .ics files compatible with Apple Calendar.

Supports:
- 课程 (course) objects with day_of_week, time_slot, week ranges, week_type
- 宜宾学院 (Yibin University) time slot mapping
- Odd/even week filtering (单/双周)
- Asia/Shanghai timezone
"""

import datetime
from typing import List, Dict, Any
from icalendar import Calendar, Event, Timezone, TimezoneStandard
from pytz import timezone

# Timezone for Yibin University (Asia/Shanghai)
TIMEZONE = timezone("Asia/Shanghai")

# Time slot mapping for 宜宾学院 (Yibin University)
TIME_SLOTS = {
    "1-2":  (datetime.time(8, 30),  datetime.time(10, 5)),
    "3-4":  (datetime.time(10, 25), datetime.time(12, 0)),
    "5-6":  (datetime.time(14, 30), datetime.time(16, 5)),
    "7-8":  (datetime.time(16, 25), datetime.time(18, 0)),
    "9-10": (datetime.time(19, 0),  datetime.time(20, 35)),
    "11":   (datetime.time(20, 45), datetime.time(21, 30)),
}


def _expand_time_slot(time_slot: str):
    """Expand a time slot like '5-8' into component slots ['5-6', '7-8'].
    Also handles single slots like '3-4' returning ['3-4']."""
    try:
        parts = time_slot.split("-")
        start, end = int(parts[0]), int(parts[1])
        if end - start <= 1:
            return [time_slot]
        # Split into 2-hour blocks
        slots = []
        for s in range(start, end, 2):
            slot = f"{s}-{s+1}"
            if slot in TIME_SLOTS:
                slots.append(slot)
            else:
                slot_alt = f"{s}-{end}"
                if slot_alt in TIME_SLOTS:
                    slots.append(slot_alt)
        return slots if slots else [time_slot]
    except (ValueError, IndexError):
        return [time_slot]


def _get_time_range(time_slot: str):
    """Return (start_time, end_time) for a time slot string like '3-4'."""
    if time_slot not in TIME_SLOTS:
        raise ValueError(
            f"Unknown time slot: '{time_slot}'. "
            f"Valid slots: {list(TIME_SLOTS.keys())}"
        )
    return TIME_SLOTS[time_slot]


def _week_matches(week_num: int, week_start: int, week_end: int, week_type: str) -> bool:
    """Check if a given week number falls within the range and matches the week type."""
    if week_num < week_start or week_num > week_end:
        return False
    if week_type == "":
        return True  # every week
    elif week_type == "单":
        return week_num % 2 == 1  # odd weeks
    elif week_type == "双":
        return week_num % 2 == 0  # even weeks
    else:
        raise ValueError(f"Unknown week_type: '{week_type}'. Use '', '单', or '双'.")


def generate_ics(courses: List[Dict[str, Any]], semester_start_date: str) -> str:
    """
    Generate an iCalendar (.ics) file string from course schedule data.

    Args:
        courses: List of course dicts, each containing:
            - course_name (str): Course name (课程名)
            - teacher (str): Teacher name (教师)
            - location (str): Classroom location (教室)
            - day_of_week (int): Day of week (1=Monday, 7=Sunday)
            - time_slot (str): Time slot, e.g. '3-4' (节次)
            - week_start (int): First week of the course (周次起始)
            - week_end (int): Last week of the course (周次结束)
            - week_type (str): '', '单' (odd), or '双' (even)

        semester_start_date: Semester start date string, e.g. '2026-02-22'
            This should be the Monday of week 1 (first teaching week).

    Returns:
        A valid .ics file string (UTF-8) that can be imported into Apple Calendar.
    """
    # Parse semester start date
    start = datetime.datetime.strptime(semester_start_date, "%Y-%m-%d")
    # Ensure it's Monday
    while start.weekday() != 0:  # 0 = Monday
        start -= datetime.timedelta(days=1)

    # Create calendar
    cal = Calendar()
    cal.add("prodid", "-//Yibin University Course Schedule//calendar_gen.py//CN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", "课程表")
    cal.add("x-wr-timezone", "Asia/Shanghai")

    # Add timezone definition
    tz = Timezone()
    tz.add("tzid", "Asia/Shanghai")
    tz.add("x-lic-location", "Asia/Shanghai")
    tzs = TimezoneStandard()
    tzs.add("dtstart", datetime.datetime(1970, 1, 1))
    tzs.add("tzoffsetfrom", datetime.timedelta(hours=8))
    tzs.add("tzoffsetto", datetime.timedelta(hours=8))
    tzs.add("tzname", "CST")
    tz.add_component(tzs)
    cal.add_component(tz)

    # Generate events for each course
    for course in courses:
        course_name = course.get("course_name", "未知课程")
        teacher = course.get("teacher", "未知教师")
        location = course.get("location", "")
        day_of_week = course["day_of_week"]
        time_slot = course["time_slot"]
        week_start = course["week_start"]
        week_end = course["week_end"]
        week_type = course.get("week_type", "")

        # Get expanded time slots (handle ranges like '5-8')
        expanded_slots = _expand_time_slot(time_slot)
        if not expanded_slots:
            continue

        for slot in expanded_slots:
            slot_start, slot_end = _get_time_range(slot)

            # Build a list of DTSTART dates for each matching week
            matching_weeks = []
            for week in range(week_start, week_end + 1):
                if _week_matches(week, week_start, week_end, week_type):
                    event_date = start + datetime.timedelta(
                        weeks=week - 1,
                        days=day_of_week - 1,
                    )
                    matching_weeks.append(event_date)

            if not matching_weeks:
                continue

            # Calculate duration from time slot
            dt_start_time = datetime.datetime.combine(matching_weeks[0], slot_start)
            dt_end_time = datetime.datetime.combine(matching_weeks[0], slot_end)
            duration = dt_end_time - dt_start_time

            # Use the first matching week as the primary DTSTART
            primary_start = datetime.datetime.combine(matching_weeks[0], slot_start)

            # Create event
            event = Event()
            event.add("dtstart", primary_start.replace(tzinfo=TIMEZONE))
            event.add("dtend", (primary_start + duration).replace(tzinfo=TIMEZONE))

            # Summary: 只显示课程名称，不包含教师
            event.add("summary", course_name)

            # Location
            if location:
                event.add("location", location)

            # Description - iCalendar标准用\n表示换行
            desc_lines = [
                f"课程: {course_name}",
                f"教师: {teacher}",
            ]
            if course.get('course_code'):
                desc_lines.append(f"课序号: {course['course_code']}")
            if location:
                desc_lines.append(f"教室: {location}")
            desc_lines.append(f"节次: {time_slot}")
            desc_lines.append(f"周次: {week_start}-{week_end}周")
            if week_type:
                desc_lines.append(f"单双周: {week_type}")
            event.add("description", "\n".join(desc_lines))

            # UID: unique identifier using the expanded slot name
            uid = f"{course_name}_{teacher}_W{day_of_week}_T{slot}_Wk{week_start}-{week_end}@yibin-edu"
            event.add("uid", uid)

            # Determine the recurrence rule
            if week_type == "":
                # Every week - simple weekly recurrence
                event.add(
                    "rrule",
                    {
                        "freq": "weekly",
                        "count": week_end - week_start + 1,
                    },
                )
            else:
                # Odd/even weeks: use weekly recurrence with interval=2
                count = len(matching_weeks)
                event.add(
                    "rrule",
                    {
                        "freq": "weekly",
                        "interval": 2,
                        "count": count,
                    },
                )

            cal.add_component(event)

    # Generate the .ics string
    ics_content = cal.to_ical()
    return ics_content.decode("utf-8")


if __name__ == "__main__":
    # Demo usage
    sample_courses = [
        {
            "course_name": "高等数学",
            "teacher": "张老师",
            "location": "教学楼A301",
            "day_of_week": 1,
            "time_slot": "1-2",
            "week_start": 1,
            "week_end": 16,
            "week_type": "",
        },
        {
            "course_name": "大学英语",
            "teacher": "李老师",
            "location": "外语楼B205",
            "day_of_week": 3,
            "time_slot": "3-4",
            "week_start": 2,
            "week_end": 17,
            "week_type": "单",
        },
    ]

    ics = generate_ics(sample_courses, "2026-02-22")
    print(ics)
    print(f"\nTotal length: {len(ics)} characters")
