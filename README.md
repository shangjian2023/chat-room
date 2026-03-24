# 课程平台 - Web 应用实验

## 技术栈
- **后端框架**: Flask 3.0
- **数据库**: MySQL + SQLAlchemy ORM
- **会话管理**: Flask-Session (服务器端 Session)
- **密码加密**: Werkzeug (generate_password_hash / check_password_hash)

## 项目结构
```
course_platform/
├── app.py              # 主应用（路由、业务逻辑）
├── requirements.txt    # Python 依赖
├── init_db.sql        # 数据库初始化脚本
├── static/            # 静态文件（CSS、JS、图片）
└── templates/         # HTML 模板
    ├── register.html  # 注册页面
    ├── login.html     # 登录页面
    └── index.html     # 课程平台主页
```

## 安装步骤

### 1. 安装 Python 依赖
```bash
cd course_platform
pip install -r requirements.txt
```

### 2. 配置 MySQL 数据库
确保 MySQL 已安装并运行，然后：

1. 登录 MySQL：
```bash
mysql -u root -p
```

2. 数据库会自动创建（首次运行时）

### 3. 修改数据库配置（如需要）
编辑 `app.py` 第 15 行，根据你的 MySQL 设置修改：
```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:你的密码@localhost:3306/course_platform?charset=utf8mb4'
```

### 4. 启动服务器
```bash
python app.py
```

服务器将在 `http://localhost:8080` 启动，支持局域网访问。

## 功能说明

### 基础功能（必做）
| 功能 | 路由 | 说明 |
|------|------|------|
| 用户注册 | `/register` | 支持表单 POST 提交，密码一致性校验 |
| 用户登录 | `/login` | 校验数据库数据，Session 会话管理 |
| 课程主页 | `/` | 需登录访问，未登录自动跳转 |
| 退出登录 | `/logout` | 清除 Session，跳转登录页 |

### 进阶功能（加分）
- ✅ 密码一致性校验（注册时两次密码比对）
- ✅ 登录/注册页面双向跳转链接
- ✅ 密码哈希加密存储（Werkzeug）
- ✅ 在线用户列表展示
- ✅ Session 会话管理（服务器端存储）

## 核心原理

### 1. 密码哈希加密
```python
# 注册时加密
password_hash = generate_password_hash(password)

# 登录时校验
check_password_hash(stored_hash, input_password)
```

### 2. Session 会话管理
- 用户登录成功后，服务器生成唯一 Session ID
- Session ID 通过 Cookie 返回给浏览器
- 后续请求自动携带 Cookie，服务器据此识别用户
- 未登录用户访问主页会被拦截并重定向到登录页

### 3. 在线用户列表
- 使用字典 `online_users` 存储当前登录用户
- 登录时添加，登出时移除
- 主页实时展示在线用户

## 测试截图
1. 注册页面
2. 登录页面
3. 数据库用户数据
4. 课程平台主页（含在线用户列表）

## 常见问题

### Q: 无法连接数据库
A: 检查 MySQL 服务是否运行，确认用户名密码正确

### Q: 端口被占用
A: 修改 `app.py` 第 130 行的 port 参数

### Q: 无法跨终端访问
A: 确保防火墙允许 8080 端口，使用 `http://IP 地址:8080` 访问
