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

# 在线用户存储
online_users = {}
anonymous_users = {}

# 聊天房间
chat_rooms = {
    'general': {'name': '公共频道', 'messages': []},
    'study': {'name': '学习交流', 'messages': []},
    'random': {'name': '水聊专区', 'messages': []}
}

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
        if user_id not in anonymous_users:
            anonymous_users[user_id] = f"网友_{str(uuid.uuid4())[:6]}"
        for room in chat_rooms.keys():
            join_room(room)
        print(f"用户 {username} 连接聊天室")

@socketio.on('disconnect')
def handle_disconnect():
    if 'user_id' in session:
        user_id = session['user_id']
        anonymous_users.pop(user_id, None)
        for room in chat_rooms.keys():
            leave_room(room)

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
    emit('online_count', {'count': len(online_users)})

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

    return render_template('index.html',
                         username=session.get('username'),
                         online_users=list(online_users.values()),
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
        online_users[user.id] = {'id': user.id, 'username': username}

        flash('登录成功', 'success')
        return redirect(url_for('index'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id and user_id in online_users:
        del online_users[user_id]
    anonymous_users.pop(user_id, None)
    session.clear()
    flash('已退出登录', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    socketio.run(app, host='0.0.0.0', port=8080, debug=True, allow_unsafe_werkzeug=True)
