import sqlite3

# 连接数据库
conn = sqlite3.connect('data/qa_database.db')
cursor = conn.cursor()

# 检查sessions表结构
print("=== sessions表结构 ===")
cursor.execute("PRAGMA table_info(sessions)")
columns = cursor.fetchall()
for column in columns:
    print(f"列名: {column[1]}, 类型: {column[2]}, 是否可为空: {column[3]}, 默认值: {column[4]}")

# 检查其他表结构
print("\n=== 所有表 ===")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
for table in tables:
    print(f"表名: {table[0]}")

# 关闭连接
conn.close()