"""
数据库初始化脚本
在 MySQL 安装完成后运行此脚本
"""
import pymysql

# 修改为你的 MySQL root 密码
MYSQL_PASSWORD = '123456'

def init_database():
    try:
        # 连接 MySQL（不指定数据库）
        conn = pymysql.connect(
            host='localhost',
            user='root',
            password=MYSQL_PASSWORD,
            charset='utf8mb4'
        )
        cursor = conn.cursor()

        # 创建数据库
        cursor.execute("CREATE DATABASE IF NOT EXISTS course_platform CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print("✓ 数据库创建成功")

        # 使用数据库
        cursor.execute("USE course_platform")

        # 创建在线用户表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS online_users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                session_id VARCHAR(256) UNIQUE NOT NULL,
                username VARCHAR(80) NOT NULL,
                login_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_active DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                ip_address VARCHAR(45),
                user_agent VARCHAR(500),
                is_active BOOLEAN DEFAULT TRUE,
                INDEX idx_user_id (user_id),
                INDEX idx_session_id (session_id),
                INDEX idx_last_active (last_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        print("✓ 在线用户表创建成功")

        # 创建用户表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(80) UNIQUE NOT NULL,
                password_hash VARCHAR(256) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        print("✓ 用户表创建成功")

        # 创建聊天消息表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(80) NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                room VARCHAR(50) DEFAULT 'general'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        print("✓ 聊天消息表创建成功")

        # 查看表结构
        cursor.execute("DESCRIBE users")
        print("\n用户表结构:")
        for row in cursor.fetchall():
            print(f"  {row}")

        conn.commit()
        cursor.close()
        conn.close()

        print("\n✓ 数据库初始化完成!")

    except pymysql.Error as e:
        print(f"✗ 数据库连接失败：{e}")
        print("请确认:")
        print("1. MySQL 服务已启动")
        print("2. root 密码正确")
        print("3. 修改脚本中的 MYSQL_PASSWORD 变量")

if __name__ == '__main__':
    init_database()
