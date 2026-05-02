import sqlite3

def check_database():
    conn = sqlite3.connect('knowledge_test.db')
    cursor = conn.cursor()
    
    print("=" * 50)
    print("Проверка базы данных")
    print("=" * 50)
    
    # Проверяем пользователей
    cursor.execute("SELECT id, username, full_name, role FROM users")
    users = cursor.fetchall()
    
    print("\nПользователи в базе данных:")
    for user in users:
        print(f"  ID: {user[0]}, Логин: {user[1]}, Имя: {user[2]}, Роль: {user[3]}")
    
    # Проверяем группы преподавателей
    cursor.execute("SELECT * FROM teacher_groups")
    groups = cursor.fetchall()
    
    print("\nГруппы преподавателей:")
    for group in groups:
        print(f"  ID: {group[0]}, Teacher ID: {group[1]}, Группа: {group[2]}")
    
    # Проверяем тесты
    cursor.execute("SELECT id, title, teacher_id FROM tests")
    tests = cursor.fetchall()
    
    print(f"\nТесты в базе: {len(tests)}")
    for test in tests:
        print(f"  ID: {test[0]}, Название: {test[1]}, Преподаватель ID: {test[2]}")
    
    conn.close()

if __name__ == "__main__":
    check_database()