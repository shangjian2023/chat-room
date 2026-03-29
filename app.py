from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import uuid

app = Flask(__name__)

# 配置密钥
app.secret_key = os.urandom(24)

# 数据库配置 - 使用 SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///course_platform.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Session 配置
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True

# 初始化扩展
db = SQLAlchemy(app)
Session(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 用户模型
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# 聊天消息模型
class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    room = db.Column(db.String(50), default='general')  # 房间字段

# 在线用户存储（内存缓存）
online_users = {}  # 缓存：user_id -> user_info
anonymous_users = {}

# 在线用户模型
class OnlineUser(db.Model):
    __tablename__ = 'online_users'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    session_id = db.Column(db.String(256), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), nullable=False)
    login_time = db.Column(db.DateTime, default=datetime.now)
    last_active = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)

# 聊天房间
chat_rooms = {
    'general': {'name': '公共频道', 'messages': []},
    'study': {'name': '学习交流', 'messages': []},
    'random': {'name': '水聊专区', 'messages': []}
}

# Session 过期时间（秒）
SESSION_TIMEOUT = 1800  # 30 分钟

# ====================
# 在线用户数据库操作
# ====================

def get_client_ip():
    """获取客户端 IP 地址"""
    if request.headers.getlist("X-Forwarded-For"):
        return request.headers.getlist("X-Forwarded-For")[0]
    return request.remote_addr

def add_online_user(user_id, username, session_id=None):
    """添加在线用户记录"""
    if not session_id:
        session_id = request.sid if hasattr(request, 'sid') else str(uuid.uuid4())

    # 检查是否已存在相同会话
    existing = OnlineUser.query.filter_by(session_id=session_id).first()
    if existing:
        existing.last_active = datetime.now()
        existing.is_active = True
        db.session.commit()
        return session_id

    # 创建新记录
    online_user = OnlineUser(
        user_id=user_id,
        username=username,
        session_id=session_id,
        ip_address=get_client_ip(),
        user_agent=request.headers.get('User-Agent', '')[:500] if request else ''
    )
    db.session.add(online_user)
    db.session.commit()
    return session_id

def remove_online_user(session_id=None, user_id=None):
    """移除在线用户记录"""
    if session_id:
        online_user = OnlineUser.query.filter_by(session_id=session_id).first()
        if online_user:
            online_user.is_active = False
            db.session.commit()
    elif user_id:
        # 登出时将该用户的所有会话设为非活动
        OnlineUser.query.filter_by(user_id=user_id, is_active=True).update({'is_active': False})
        db.session.commit()

def update_user_activity(session_id):
    """更新用户最后活跃时间"""
    online_user = OnlineUser.query.filter_by(session_id=session_id).first()
    if online_user:
        online_user.last_active = datetime.now()
        db.session.commit()

def get_online_users_count():
    """获取在线用户数量（5 分钟内有活动的）"""
    from datetime import timedelta
    threshold = datetime.now() - timedelta(minutes=5)
    return OnlineUser.query.filter(
        OnlineUser.is_active == True,
        OnlineUser.last_active >= threshold
    ).distinct(OnlineUser.user_id).count()

def get_online_users_list():
    """获取在线用户列表"""
    from datetime import timedelta
    threshold = datetime.now() - timedelta(minutes=5)
    # 按 user_id 分组，取每个用户最新的记录
    subquery = db.session.query(
        db.func.max(OnlineUser.id).label('max_id')
    ).filter(
        OnlineUser.is_active == True,
        OnlineUser.last_active >= threshold
    ).group_by(OnlineUser.user_id).subquery()

    online_users = OnlineUser.query.join(
        subquery, OnlineUser.id == subquery.c.max_id
    ).all()
    return [{'user_id': u.user_id, 'username': u.username} for u in online_users]

def cleanup_stale_sessions():
    """清理过期会话（超过 30 分钟无活动）"""
    from datetime import timedelta
    threshold = datetime.now() - timedelta(minutes=30)
    OnlineUser.query.filter(
        OnlineUser.is_active == True,
        OnlineUser.last_active < threshold
    ).update({'is_active': False})
    db.session.commit()

# 初始化数据库
def init_db():
    with app.app_context():
        db.create_all()
        print("数据库表已创建")

# WebSocket 聊天事件
@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        user_id = session['user_id']
        username = session.get('username', '匿名用户')
        # 添加在线用户记录
        session_id = request.sid
        add_online_user(user_id, username, session_id)

        if user_id not in anonymous_users:
            anonymous_users[user_id] = f"网友_{str(uuid.uuid4())[:6]}"

        for room in chat_rooms.keys():
            join_room(room)

        # 广播更新在线人数
        online_count = get_online_users_count()
        emit('online_count', {'count': online_count}, broadcast=True)
        print(f"用户 {username} 连接聊天室，当前在线：{online_count}")

@socketio.on('disconnect')
def handle_disconnect():
    if 'user_id' in session:
        user_id = session['user_id']
        session_id = request.sid
        anonymous_users.pop(user_id, None)

        for room in chat_rooms.keys():
            leave_room(room)

        # 更新数据库，不立即删除，标记为非活动
        remove_online_user(session_id=session_id)

        # 广播更新在线人数
        online_count = get_online_users_count()
        emit('online_count', {'count': online_count}, broadcast=True)

@socketio.on('heartbeat')
def handle_heartbeat():
    """心跳包，更新活跃时间"""
    if 'user_id' in session:
        session_id = request.sid
        update_user_activity(session_id)

@socketio.on('send_message')
def handle_message(data):
    if 'user_id' not in session:
        return

    message = data.get('message', '').strip()
    if not message:
        return

    user_id = session['user_id']
    username = session.get('username', '匿名用户')
    use_anonymous = data.get('anonymous', False)
    room = data.get('room', 'general')

    if use_anonymous:
        if user_id not in anonymous_users:
            anonymous_users[user_id] = f"网友_{str(uuid.uuid4())[:6]}"
        display_name = anonymous_users[user_id]
    else:
        display_name = username

    # 保存到数据库
    chat_msg = ChatMessage(username=display_name, message=message, room=room)
    db.session.add(chat_msg)
    db.session.commit()

    # 广播消息
    emit('receive_message', {
        'username': display_name,
        'message': message,
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'is_anonymous': use_anonymous,
        'is_self': True,
        'room': room
    }, broadcast=True, room=room)

@socketio.on('get_online_count')
def handle_online_count():
    count = get_online_users_count()
    emit('online_count', {'count': count})

@socketio.on('get_messages')
def handle_get_messages():
    """获取所有消息（默认房间）"""
    messages = ChatMessage.query.order_by(ChatMessage.timestamp.desc()).limit(50).all()
    messages.reverse()
    emit('receive_messages', [{
        'username': m.username,
        'message': m.message,
        'timestamp': m.timestamp.strftime('%H:%M:%S'),
        'room': m.room or 'general'
    } for m in messages])

@socketio.on('get_room_messages')
def handle_get_room_messages(data):
    """获取指定房间的消息"""
    room = data.get('room', 'general')
    messages = ChatMessage.query.filter_by(room=room).order_by(ChatMessage.timestamp.desc()).limit(50).all()
    messages.reverse()
    emit('receive_messages', [{
        'username': m.username,
        'message': m.message,
        'timestamp': m.timestamp.strftime('%H:%M:%S'),
        'room': m.room or 'general'
    } for m in messages])

@socketio.on('join_room')
def handle_join_room_event(data):
    """加入房间"""
    room = data.get('room', 'general')
    if room in chat_rooms:
        join_room(room)
        emit('room_joined', {'room': room, 'room_name': chat_rooms[room]['name']})

# 路由
@app.route('/')
def index():
    if 'user_id' not in session:
        flash('请先登录', 'warning')
        return redirect(url_for('login'))

    messages = ChatMessage.query.order_by(ChatMessage.timestamp.desc()).limit(50).all()
    messages.reverse()

    # 从数据库获取在线用户列表
    online_users_list = get_online_users_list()

    return render_template('index.html',
                         username=session.get('username'),
                         online_users=online_users_list,
                         messages=messages)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not username or not password:
            flash('用户名和密码不能为空', 'error')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('两次输入的密码不一致', 'error')
            return redirect(url_for('register'))

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('用户名已存在', 'error')
            return redirect(url_for('register'))

        new_user = User(username=username)
        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash('注册成功，请登录', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'注册失败：{str(e)}', 'error')

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('用户名和密码不能为空', 'error')
            return redirect(url_for('login'))

        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            flash('用户名或密码错误', 'error')
            return redirect(url_for('login'))

        session['user_id'] = user.id
        session['username'] = user.username

        # 添加到在线用户数据库
        add_online_user(user.id, username)

        flash('登录成功', 'success')
        return redirect(url_for('index'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    session_id = request.sid if hasattr(request, 'sid') else None

    # 更新数据库中的在线状态
    remove_online_user(session_id=session_id, user_id=user_id)

    anonymous_users.pop(user_id, None)
    session.clear()

    flash('已退出登录', 'info')
    return redirect(url_for('login'))

@app.route('/admin')
def admin():
    """管理页面 - 查看在线用户"""
    # 获取所有在线用户记录（包括非活动的）
    all_users = OnlineUser.query.order_by(OnlineUser.last_active.desc()).limit(100).all()

    # 统计
    from datetime import timedelta
    threshold = datetime.now() - timedelta(minutes=5)
    active_sessions = OnlineUser.query.filter(
        OnlineUser.is_active == True,
        OnlineUser.last_active >= threshold
    ).count()

    total_sessions = len(all_users)

    return render_template('admin.html',
                         online_users=all_users,
                         total_sessions=total_sessions,
                         active_sessions=active_sessions)

if __name__ == '__main__':
    import threading

    def cleanup_task():
        """定期清理过期会话"""
        while True:
            import time
            time.sleep(300)  # 每 5 分钟清理一次
            with app.app_context():
                cleanup_stale_sessions()
                print("已清理过期会话")

    # 启动后台清理线程
    cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
    cleanup_thread.start()

    init_db()
    socketio.run(app, host='0.0.0.0', port=8080, debug=True, allow_unsafe_werkzeug=True)
