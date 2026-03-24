-- 创建数据库
CREATE DATABASE IF NOT EXISTS course_platform CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 使用数据库
USE course_platform;

-- 查看已创建的表
SHOW TABLES;

-- 查看用户表结构
DESCRIBE users;

-- 查询所有注册用户
SELECT * FROM users;
