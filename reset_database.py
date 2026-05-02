import sqlite3
import hashlib
import os

def reset_database():
    # Удаляем старую базу
    if os.path.exists('knowledge_test.db'):
        os.remove('knowledge_test.db')
        print("✓ Старая база данных удалена")
    
    # Создаем новую базу
    conn = sqlite3.connect('knowledge_test.db')
    cursor = conn.cursor()
    
    # 1. Таблица пользователей
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL,
            group_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✓ Таблица users создана")
    
    # 2. Таблица тестов
    cursor.execute('''
        CREATE TABLE tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            teacher_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (teacher_id) REFERENCES users (id)
        )
    ''')
    print("✓ Таблица tests создана")
    
    # 3. Таблица вопросов
    cursor.execute('''
        CREATE TABLE questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            points INTEGER DEFAULT 1,
            FOREIGN KEY (test_id) REFERENCES tests (id) ON DELETE CASCADE
        )
    ''')
    print("✓ Таблица questions создана")
    
    # 4. Таблица ответов
    cursor.execute('''
        CREATE TABLE answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            answer_text TEXT NOT NULL,
            is_correct BOOLEAN DEFAULT 0,
            FOREIGN KEY (question_id) REFERENCES questions (id) ON DELETE CASCADE
        )
    ''')
    print("✓ Таблица answers создана")
    
    # 5. Таблица результатов
    cursor.execute('''
        CREATE TABLE test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            score INTEGER,
            max_score INTEGER,
            percentage REAL,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (test_id) REFERENCES tests (id),
            FOREIGN KEY (student_id) REFERENCES users (id),
            UNIQUE(test_id, student_id)
        )
    ''')
    print("✓ Таблица test_results создана")
    
    # 6. Таблица ответов студентов
    cursor.execute('''
        CREATE TABLE student_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            result_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            answer_id INTEGER,
            is_correct BOOLEAN,
            FOREIGN KEY (result_id) REFERENCES test_results (id),
            FOREIGN KEY (question_id) REFERENCES questions (id),
            FOREIGN KEY (answer_id) REFERENCES answers (id)
        )
    ''')
    print("✓ Таблица student_answers создана")
    
    # Добавляем тестовых пользователей
    users = [
        ("admin", "admin123", "Системный администратор", "admin", None),
        ("teacher", "teacher123", "Иванов Иван Иванович", "teacher", None),
        ("student1", "student123", "Петров Петр Петрович", "student", "ИС-21"),
        ("student2", "student123", "Сидорова Анна Сергеевна", "student", "ИС-21"),
    ]
    
    for username, password, full_name, role, group_name in users:
        hashed = hashlib.sha256(password.encode()).hexdigest()
        try:
            cursor.execute('''
                INSERT INTO users (username, password, full_name, role, group_name)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, hashed, full_name, role, group_name))
            print(f"✓ Добавлен пользователь: {username} ({role})")
        except sqlite3.IntegrityError:
            print(f"✗ Пользователь {username} уже существует")
    
    conn.commit()
    conn.close()
    
    print("\n" + "="*50)
    print("База данных успешно создана!")
    print("="*50)
    print("\nУчетные данные для входа:")
    print("  👨‍🏫 Преподаватель: teacher / teacher123")
    print("  👨‍🎓 Студент 1: student1 / student123")
    print("  👩‍🎓 Студент 2: student2 / student123")
    print("  👑 Администратор: admin / admin123")

if __name__ == "__main__":
    reset_database()
    
    