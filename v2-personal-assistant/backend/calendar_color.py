"""
课表颜色管理 - 自动分配颜色并导入苹果日历
"""
import subprocess, json, os, tempfile, datetime
from icalendar import Calendar, Event, Timezone, TimezoneStandard
from pytz import timezone

TIMEZONE = timezone("Asia/Shanghai")
TIME_SLOTS = {
    "1-2":  (datetime.time(8, 30),  datetime.time(10, 5)),
    "3-4":  (datetime.time(10, 25), datetime.time(12, 0)),
    "5-6":  (datetime.time(14, 30), datetime.time(16, 5)),
    "7-8":  (datetime.time(16, 25), datetime.time(18, 0)),
    "9-10": (datetime.time(19, 0),  datetime.time(20, 35)),
    "11":   (datetime.time(20, 45), datetime.time(21, 30)),
}

# 颜色色板 (名称, RGB 0-255)
COLOR_PALETTE = [
    ("红色",     (255, 59, 48)),
    ("橙色",     (255, 149, 0)),
    ("黄色",     (255, 204, 0)),
    ("绿色",     (52, 199, 89)),
    ("薄荷",     (0, 199, 190)),
    ("青色",     (48, 176, 199)),
    ("天蓝",     (0, 122, 255)),
    ("靛蓝",     (88, 86, 214)),
    ("紫色",     (175, 82, 222)),
    ("粉色",     (255, 45, 85)),
    ("玫红",     (255, 105, 180)),
    ("珊瑚",     (255, 127, 80)),
    ("棕色",     (162, 132, 94)),
    ("深蓝",     (0, 56, 128)),
    ("墨绿",     (0, 128, 0)),
    ("酒红",     (128, 0, 32)),
    ("翡翠",     (80, 200, 120)),
    ("松石",     (64, 224, 208)),
    ("薰衣草",   (180, 140, 220)),
    ("橄榄",     (128, 128, 0)),
]

def rgb_to_ascolor(r, g, b):
    """RGB → AppleScript color {R16, G16, B16}"""
    return f"{{{round(r/255*65535)}, {round(g/255*65535)}, {round(b/255*65535)}}}"

def decode_existing_color(val):
    """解析Apple Calendar返回的64位颜色值为RGB"""
    # 格式: 00RRRRRRGGGGGGBBBBBB (16位每通道) 
    b = val & 0xFFFF
    g = (val >> 16) & 0xFFFF
    r = (val >> 32) & 0xFFFF
    return (r / 65535 * 255, g / 65535 * 255, b / 65535 * 255)

def get_existing_calendar_colors():
    """读取现有的日历名称和颜色"""
    try:
        result = subprocess.run(
            ['osascript', '-e', '''
                tell application "Calendar"
                    set output to ""
                    repeat with c in calendars
                        set output to output & name of c & "|" & color of c & return
                    end repeat
                    return output
                end tell
            '''],
            capture_output=True, text=True, timeout=10
        )
        existing = {}
        for line in result.stdout.strip().split('\n'):
            if '|' in line:
                parts = line.split('|', 1)
                existing[parts[0].strip()] = int(parts[1].strip())
        return existing
    except:
        return {}

def assign_colors(courses, existing_calendars=None):
    """为课程分配不重复的颜色"""
    if existing_calendars is None:
        existing_calendars = get_existing_calendar_colors()
    
    # 把现有颜色转为近似色板索引，方便去重
    existing_near = set()
    for _, val in existing_calendars.items():
        r, g, b = decode_existing_color(val)
        # 找最近的色板颜色
        for i, (cn, (cr, cg, cb)) in enumerate(COLOR_PALETTE):
            dist = ((r-cr)**2 + (g-cg)**2 + (b-cb)**2)**0.5
            if dist < 60:  # 近似匹配
                existing_near.add(i)
    
    unique_courses = list(dict.fromkeys(c.get('course_name','未知') for c in courses))
    
    color_map = {}
    used_indices = set(existing_near)
    
    for i, name in enumerate(unique_courses):
        idx = i
        while idx in used_indices:
            idx += 1
            if idx >= len(COLOR_PALETTE):
                idx = 0  # 回绕
        
        used_indices.add(idx)
        cn, rgb = COLOR_PALETTE[idx]
        r, g, b = rgb
        color_map[name] = {
            'name': cn,
            'hex': f'#{r:02x}{g:02x}{b:02x}',
            'as_color': rgb_to_ascolor(r, g, b),
            'rgb': rgb
        }
    
    return color_map

def generate_ics_for_course(course_name, events, semester_start, color_hex=None):
    """为单个课程生成ICS"""
    start = datetime.datetime.strptime(semester_start, "%Y-%m-%d")
    while start.weekday() != 0:
        start -= datetime.timedelta(days=1)
    
    cal = Calendar()
    cal.add("prodid", f"-//Personal Assistant//{course_name}//CN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", f"课表-{course_name}")
    
    # 添加 Apple 颜色属性（iPhone 可识别）
    if color_hex:
        cal.add("x-apple-calendar-color", color_hex)
    
    for ce in events:
        slot = TIME_SLOTS.get(ce['time_slot'], (datetime.time(8,0), datetime.time(9,0)))
        ws, we = ce['week_start'], ce['week_end']
        wt = ce.get('week_type', '')
        dow = int(ce['day_of_week'])
        
        for week in range(ws, we + 1):
            if wt == '单' and week % 2 == 0: continue
            if wt == '双' and week % 2 == 1: continue
            d = start + datetime.timedelta(weeks=week-1, days=dow-1)
            
            event = Event()
            event.add("uid", f"{ce.get('course_code','')}_{d.strftime('%Y%m%d')}_{ce['time_slot']}@yibin")
            event.add("dtstart", datetime.datetime.combine(d, slot[0]).replace(tzinfo=TIMEZONE))
            event.add("dtend", datetime.datetime.combine(d, slot[1]).replace(tzinfo=TIMEZONE))
            event.add("summary", f"{ce['course_name']}")
            if ce.get('location'):
                event.add("location", ce['location'])
            
            desc = f"课程: {ce['course_name']}"
            if ce.get('teacher'): desc += f"\n教师: {ce['teacher']}"
            if ce.get('location'): desc += f"\n教室: {ce['location']}"
            desc += f"\n节次: {ce['time_slot']}"
            event.add("description", desc)
            cal.add_component(event)
    
    return cal.to_ical().decode('utf-8')

def export_with_colors(courses, semester_start='2026-03-02'):
    """主流程：分配颜色 + 创建日历 + 导入"""
    existing = get_existing_calendar_colors()
    print(f"📋 已有 {len(existing)} 个日历")
    
    color_map = assign_colors(courses, existing)
    
    # 按课程分组
    groups = {}
    for c in courses:
        name = c.get('course_name', '未知')
        groups.setdefault(name, []).append(c)
    
    # 创建日历 & ICS
    ics_dir = os.path.expanduser("~/课表导入")
    os.makedirs(ics_dir, exist_ok=True)
    
    for course_name, events in groups.items():
        ci = color_map.get(course_name)
        if not ci: continue
        
        cal_name = f"课表-{course_name}"
        
        # 创建日历（如不存在）
        if cal_name not in existing:
            script = f'''
            tell application "Calendar"
                set newCal to make new calendar with properties {{name:"{cal_name}"}}
                set color of newCal to {ci['as_color']}
            end tell
            '''
            r = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                print(f"  ✅ 创建日历 [{cal_name}] 颜色={ci['name']}")
            else:
                print(f"  ⚠️ {r.stderr.strip()}")
        
        # 生成ICS
        ics_path = os.path.join(ics_dir, f"{course_name}.ics")
        with open(ics_path, 'w', encoding='utf-8') as f:
            f.write(generate_ics_for_course(course_name, events, semester_start, color_hex=ci['hex']))
    
    # 全部打开导入
    print(f"\n📂 打开ICS文件导入日历...")
    for course_name in groups:
        ics_path = os.path.join(ics_dir, f"{course_name}.ics")
        subprocess.run(['open', ics_path])
    
    print(f"\n✅ 完成！颜色分配：")
    for name, ci in color_map.items():
        print(f"   {ci['name']:4s} {ci['hex']} → {name}")


def generate_colored_ics_files(courses, semester_start='2026-03-02'):
    """
    生成按课程分色的 .ics 文件，返回 (文件路径列表, 颜色映射)
    不打开Finder，适合从Web API调用
    """
    existing = get_existing_calendar_colors()
    color_map = assign_colors(courses, existing)
    
    # 按课程分组
    groups = {}
    for c in courses:
        name = c.get('course_name', '未知')
        groups.setdefault(name, []).append(c)
    
    # 创建日历（自动检测避免颜色冲突）
    created_cals = []
    for course_name in groups:
        ci = color_map.get(course_name)
        if not ci:
            continue
        cal_name = f"课表-{course_name}"
        if cal_name not in existing:
            script = f'''
            tell application "Calendar"
                set newCal to make new calendar with properties {{name:"{cal_name}"}}
                set color of newCal to {ci['as_color']}
            end tell
            '''
            subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=10)
            created_cals.append(cal_name)
    
    # 生成 .ics 文件
    out_dir = tempfile.mkdtemp(prefix='yibin_schedule_')
    ics_files = []
    
    for course_name, events in groups.items():
        ci = color_map.get(course_name)
        if not ci:
            continue
        safe_name = course_name.replace('/', '_').replace(':', '_')
        ics_path = os.path.join(out_dir, f"{safe_name}.ics")
        with open(ics_path, 'w', encoding='utf-8') as f:
            f.write(generate_ics_for_course(course_name, events, semester_start, color_hex=ci['hex']))
        ics_files.append(ics_path)
    
    return ics_files, color_map, created_cals

if __name__ == '__main__':
    test = [
        {"course_name":"EDA技术及应用","teacher":"李嘉勋","location":"八号楼409","day_of_week":1,"time_slot":"1-2","week_start":2,"week_end":17,"week_type":"单"},
        {"course_name":"信号与系统","teacher":"雷建超","location":"八号楼413","day_of_week":4,"time_slot":"1-2","week_start":2,"week_end":18,"week_type":""},
        {"course_name":"马原","teacher":"易琳","location":"八号楼302","day_of_week":2,"time_slot":"3-4","week_start":2,"week_end":18,"week_type":""},
        {"course_name":"概率论","teacher":"文相容","location":"7C305","day_of_week":3,"time_slot":"3-4","week_start":3,"week_end":17,"week_type":"单"},
        {"course_name":"体育4(足球)","teacher":"程凡","location":"操场24","day_of_week":1,"time_slot":"5-6","week_start":2,"week_end":17,"week_type":""},
        {"course_name":"形势与政策3","teacher":"彭维聪","location":"7C205","day_of_week":3,"time_slot":"5-8","week_start":9,"week_end":10,"week_type":""},
        {"course_name":"摄影技术(网)","teacher":"段丽莎","location":"八号楼201","day_of_week":4,"time_slot":"7-8","week_start":2,"week_end":18,"week_type":""},
    ]
    export_with_colors(test)
