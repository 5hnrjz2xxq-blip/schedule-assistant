"""
Personal Assistant - 宜宾学院课表助手 (macOS 桌面版)
通过 Node.js 子进程维护浏览器会话，解决验证码跨页面问题
"""
import os, json, subprocess, sys, threading
from flask import Flask, render_template, request, jsonify

PROJECT_DIR = os.path.expanduser('~/personal-assistant')
BACKEND_DIR = os.path.join(PROJECT_DIR, 'backend')
TEMPLATE_DIR = os.path.join(PROJECT_DIR, 'frontend')
SESSION_JS = os.path.join(BACKEND_DIR, 'browser_session.js')

sys.path.insert(0, BACKEND_DIR)
from calendar_color import generate_colored_ics_files

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=TEMPLATE_DIR)

# ── 浏览器会话管理 ──
class SessionManager:
    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()
        self.queue = []  # 待发送命令
        self.responses = []
        
    def start(self):
        if self.proc and self.proc.poll() is None:
            return True
        self.proc = subprocess.Popen(
            ['node', SESSION_JS],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=BACKEND_DIR, text=True, bufsize=1
        )
        # 等待 ready 信号
        import time
        time.sleep(2)
        return self.proc.poll() is None
    
    def send(self, command, timeout=60):
        """发送命令并等待响应"""
        with self.lock:
            if not self.proc or self.proc.poll() is not None:
                self.start()
            
            try:
                self.proc.stdin.write(command + '\n')
                self.proc.stdin.flush()
            except:
                return {'error': '进程已退出'}
            
            # 读取响应（阻塞等待）
            import time
            start = time.time()
            while time.time() - start < timeout:
                line = self.proc.stdout.readline()
                if line:
                    try:
                        return json.loads(line.strip())
                    except:
                        continue
            return {'error': '超时'}
    
    def reset(self):
        self.send('reset')
    
    def quit(self):
        if self.proc:
            try: self.proc.stdin.write('quit\n'); self.proc.stdin.flush()
            except: pass
            self.proc.wait(timeout=5)

session = SessionManager()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/start')
def api_start():
    """启动浏览器会话并获取验证码"""
    if not session.start():
        return jsonify({'success': False, 'message': '浏览器启动失败'})
    result = session.send('start', timeout=30)
    return jsonify(result)

@app.route('/api/captcha')
def get_captcha():
    """获取验证码（会话已启动时）"""
    result = session.send('captcha', timeout=10)
    return jsonify(result)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    captcha = data.get('captcha', '')
    if not username or not password:
        return jsonify({'success': False, 'message': '请输入学号和密码'})
    result = session.send(f'login {username} {password} {captcha}', timeout=60)
    return jsonify(result)

@app.route('/api/extract', methods=['POST'])
def extract():
    """提取课表数据"""
    result = session.send('extract', timeout=90)
    return jsonify(result)

@app.route('/api/export-ics', methods=['POST'])
def export_ics():
    data = request.json
    courses = data.get('courses', [])
    semester_start = data.get('semester_start', '2026-03-02')
    if not courses:
        return jsonify({'success': False, 'message': '没有课表数据'})
    try:
        ics_files, color_map, created_cals = generate_colored_ics_files(courses, semester_start)
        for ics_path in ics_files:
            subprocess.run(['open', ics_path], timeout=5)
        color_summary = {}
        for c in courses:
            name = c.get('full', c.get('course_name', '未知'))
            if name in color_map:
                color_summary[name] = color_map[name]['name']
        return jsonify({
            'success': True,
            'message': f'已生成 {len(ics_files)} 个课表文件',
            'files': len(ics_files),
            'colors': color_summary
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/semester-info')
def semester_info():
    return jsonify({'success': True, 'semester_start': '2026-03-02', 'source': '校历'})

@app.route('/api/reset')
def api_reset():
    session.reset()
    return jsonify({'success': True})

if __name__ == '__main__':
    print("🚀 宜宾学院课表助手 (macOS 桌面版)")
    print("📱 打开浏览器访问: http://localhost:8080")
    try:
        app.run(debug=False, host='127.0.0.1', port=8080)
    finally:
        session.quit()
