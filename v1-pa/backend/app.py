"""
Personal Assistant - 宜宾学院课表助手
Flask后端应用
"""
import sys
import os
import json
import subprocess
import tempfile
import logging
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from calendar_gen import generate_ics
except ImportError as e:
    logger.warning(f"calendar_gen module not found: {e}. ICS export will be disabled.")
    generate_ics = None

app = Flask(__name__, 
            template_folder='../frontend',
            static_folder='../frontend')

# 全局存储登录状态和课表数据
user_sessions = {}


@app.route('/')
def index():
    """主页"""
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error rendering index: {e}")
        return jsonify({'error': 'Frontend not available'}), 500


@app.route('/api/test')
def test_endpoint():
    """测试端点 - 返回模拟课程数据用于前端测试"""
    mock_courses = [
        {
            'name': '高等数学',
            'teacher': '张老师',
            'location': '教学楼A-301',
            'weekday': '1',
            'start_section': '1',
            'end_section': '2',
            'weeks': '1-16'
        },
        {
            'name': '大学英语',
            'teacher': '李老师',
            'location': '外语楼B-205',
            'weekday': '2',
            'start_section': '3',
            'end_section': '4',
            'weeks': '1-16'
        },
        {
            'name': '计算机基础',
            'teacher': '王老师',
            'location': '实验楼C-102',
            'weekday': '3',
            'start_section': '5',
            'end_section': '6',
            'weeks': '1-16'
        },
        {
            'name': '思想政治',
            'teacher': '刘老师',
            'location': '教学楼D-401',
            'weekday': '4',
            'start_section': '1',
            'end_section': '2',
            'weeks': '1-12'
        },
        {
            'name': '体育',
            'teacher': '陈老师',
            'location': '体育馆',
            'weekday': '5',
            'start_section': '7',
            'end_section': '8',
            'weeks': '1-16'
        }
    ]
    logger.info("Test endpoint accessed, returning mock course data")
    return jsonify({
        'success': True,
        'data': mock_courses,
        'message': 'Mock data for testing'
    })


@app.route('/api/login', methods=['POST'])
def login():
    """登录接口 - 使用Playwright浏览器自动化"""
    data = request.json
    if not data:
        logger.warning("Login attempt with empty body")
        return jsonify({'success': False, 'message': '请求数据不能为空'}), 400
    
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        logger.warning("Login attempt with missing credentials")
        return jsonify({'success': False, 'message': '请输入学号和密码'}), 400
    
    try:
        # 调用Node.js Playwright爬虫 - 使用.cjs文件
        scraper_path = os.path.join(os.path.dirname(__file__), 'scraper.cjs')
        
        if not os.path.exists(scraper_path):
            logger.error(f"Scraper file not found: {scraper_path}")
            return jsonify({'success': False, 'message': '服务端配置错误，请联系管理员'}), 500
        
        logger.info(f"Starting scraper for user: {username[:4]}****")
        
        result = subprocess.run(
            ['node', scraper_path, username, password],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else '登录失败'
            logger.error(f"Scraper failed with code {result.returncode}: {error_msg}")
            return jsonify({'success': False, 'message': error_msg}), 500
        
        if not result.stdout.strip():
            logger.error("Scraper returned empty output")
            return jsonify({'success': False, 'message': '爬虫未返回数据，请重试'}), 500
        
        # 解析爬虫输出
        try:
            courses = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse scraper output: {e}")
            logger.debug(f"Raw output: {result.stdout[:500]}")
            return jsonify({'success': False, 'message': '数据解析失败，请重试'}), 500
        
        if not isinstance(courses, list):
            logger.error(f"Unexpected data format: {type(courses)}")
            return jsonify({'success': False, 'message': '数据格式错误'}), 500
        
        # 存储课表数据
        user_sessions[username] = {
            'courses': courses,
            'password': password
        }
        
        logger.info(f"Login successful for user: {username[:4]}****, got {len(courses)} courses")
        return jsonify({'success': True, 'message': '登录成功'})
        
    except subprocess.TimeoutExpired:
        logger.error("Scraper timed out after 60 seconds")
        return jsonify({'success': False, 'message': '登录超时，请重试'}), 504
    except FileNotFoundError:
        logger.error("Node.js not found in PATH")
        return jsonify({'success': False, 'message': '服务端环境配置错误'}), 500
    except Exception as e:
        logger.error(f"Unexpected error during login: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'登录失败: {str(e)}'}), 500


@app.route('/api/schedule')
def get_schedule():
    """获取课表接口"""
    # 使用最近登录的用户数据
    if not user_sessions:
        return jsonify({'success': False, 'message': '请先登录'}), 401
    
    # 获取最新的用户数据
    username = list(user_sessions.keys())[-1]
    courses = user_sessions[username]['courses']
    
    logger.info(f"Schedule requested, returning {len(courses)} courses")
    return jsonify({'success': True, 'data': courses})


@app.route('/api/export-ics', methods=['POST'])
def export_ics():
    """导出ICS文件"""
    data = request.json
    courses = data.get('courses', []) if data else []
    semester_start = data.get('semester_start', '2024-09-02') if data else '2024-09-02'
    
    if not courses:
        return jsonify({'success': False, 'message': '没有课表数据'}), 400
    
    if generate_ics is None:
        return jsonify({'success': False, 'message': 'ICS导出功能暂不可用'}), 500
    
    temp_path = None
    try:
        # 生成ICS内容
        ics_content = generate_ics(courses, semester_start)
        
        # 保存到临时文件
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.ics', delete=False) as f:
            f.write(ics_content.encode('utf-8'))
            temp_path = f.name
        
        logger.info(f"Generated ICS file with {len(courses)} courses")
        return send_file(temp_path, 
                        as_attachment=True,
                        download_name='宜宾学院课程表.ics',
                        mimetype='text/calendar')
    except Exception as e:
        logger.error(f"Failed to export ICS: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'导出失败: {str(e)}'}), 500


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {e}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    logger.info("🚀 启动宜宾学院课表助手...")
    logger.info("📱 请在浏览器中打开: http://localhost:8080")
    logger.info("按 Ctrl+C 停止服务")
    app.run(debug=True, host='0.0.0.0', port=8080)
