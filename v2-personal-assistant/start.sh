#!/bin/bash
# 宜宾学院课表助手
# 用法: ./start.sh                # 启动Web界面
#        ./start.sh 学号 密码      # 直接爬取+导出日历

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

if [ $# -ge 2 ]; then
  echo "📚 正在爬取课表..."
  result=$(node backend/scraper_prod.cjs "$1" "$2" 2>/dev/null)
  echo "$result" | python3 -c "
import json, sys
sys.path.insert(0, 'backend')
from calendar_gen import generate_ics
d = json.load(sys.stdin)
if d.get('success') and d.get('courses'):
    ics = generate_ics(d['courses'], '2026-03-02')
    with open('${1}_课表.ics', 'w', encoding='utf-8') as f:
        f.write(ics)
    print(f'✅ 已生成 {d[\"count\"]}门课的日历文件: {d[\"courses\"][0][\"course_name\"]}.ics')
    print('📱 双击 课表.ics 导入苹果日历')
else:
    print('❌', d.get('error', '失败'))
" 2>/dev/null
  exit 0
fi

lsof -ti:8080 2>/dev/null | xargs kill -9 2>/dev/null
echo "🚀 宜宾学院课表助手"
echo "📱 http://localhost:8080"
echo ""
python3 backend/app.py
