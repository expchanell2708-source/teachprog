# database.py
import sqlite3
import hashlib
from contextlib import contextmanager
from config import Config

class Database:
    def __init__(self):
        self.db_path = Config.DATABASE_PATH
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_db(self):
        """Инициализация базы данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Пользователи
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    group_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица для хранения групп преподавателя
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teacher_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_id INTEGER NOT NULL,
                    group_name TEXT NOT NULL,
                    FOREIGN KEY (teacher_id) REFERENCES users (id) ON DELETE CASCADE,
                    UNIQUE(teacher_id, group_name)
                )
            ''')
            
            # Тесты
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    teacher_id INTEGER NOT NULL,
                    target_groups TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (teacher_id) REFERENCES users (id)
                )
            ''')
            
            # Вопросы теста
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_id INTEGER NOT NULL,
                    question_text TEXT NOT NULL,
                    points INTEGER DEFAULT 1,
                    FOREIGN KEY (test_id) REFERENCES tests (id) ON DELETE CASCADE
                )
            ''')
            
            # Варианты ответов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL,
                    answer_text TEXT NOT NULL,
                    is_correct BOOLEAN DEFAULT 0,
                    FOREIGN KEY (question_id) REFERENCES questions (id) ON DELETE CASCADE
                )
            ''')
            
            # Результаты прохождения тестов студентами
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS test_results (
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
            
            # Детальные ответы студента
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS student_answers (
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
            
            # Добавляем тестовых пользователей ТОЛЬКО если таблица users пуста
            self._add_test_users_if_empty(cursor)
    
    def _add_test_users_if_empty(self, cursor):
        """Добавление тестовых пользователей только если таблица пуста"""
        # Проверяем, есть ли пользователи в базе
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        
        if count == 0:
            print("База данных пуста. Добавляем тестовых пользователей...")
            self._add_test_users(cursor)
        else:
            print(f"В базе данных уже есть {count} пользователь(ей). Тестовые пользователи не добавлены.")
    
    def _add_test_users(self, cursor):
        """Добавление тестовых пользователей (только при первом запуске)"""
        users = [
            ("admin", "admin123", "Системный администратор", "admin", None),
            ("admin2", "admin123", "Петров Админ Админович", "admin", None),
            ("teacher", "teacher123", "Иванов Иван Иванович", "teacher", None),
            ("teacher2", "teacher123", "Смирнова Елена Петровна", "teacher", None),
            ("student", "student123", "Баров Данила Михайлович", "student", "1"),
            ("student1", "student123", "Петров Петр Петрович", "student", "2"),
            ("student2", "student123", "Авав Ава Ававав", "student", "3"),
            ("student3", "student123", "Кузнецов Алексей Дмитриевич", "student", "ИС-22"),
        ]
        
        for username, password, full_name, role, group_name in users:
            hashed = hashlib.sha256(password.encode()).hexdigest()
            try:
                cursor.execute('''
                    INSERT INTO users (username, password, full_name, role, group_name)
                    VALUES (?, ?, ?, ?, ?)
                ''', (username, hashed, full_name, role, group_name))
                print(f"  Добавлен пользователь: {username} ({role})")
            except sqlite3.IntegrityError:
                print(f"  Пользователь {username} уже существует")
        
        # Добавляем группы для преподавателей (назначает администратор)
        # Сначала получаем ID преподавателей
        cursor.execute("SELECT id FROM users WHERE username='teacher'")
        teacher = cursor.fetchone()
        cursor.execute("SELECT id FROM users WHERE username='teacher2'")
        teacher2 = cursor.fetchone()
        
        if teacher and teacher2:
            teacher_groups = [
                (teacher['id'], "1"),
                (teacher['id'], "2"),
                (teacher['id'], "3"),
                (teacher2['id'], "1"),
            ]
            
            for teacher_id, group_name in teacher_groups:
                try:
                    cursor.execute('''
                        INSERT INTO teacher_groups (teacher_id, group_name)
                        VALUES (?, ?)
                    ''', (teacher_id, group_name))
                    print(f"  Добавлена группа {group_name} для преподавателя ID {teacher_id}")
                except sqlite3.IntegrityError:
                    pass
        
        # Добавляем пример теста для демонстрации (если нет тестов)
        cursor.execute('SELECT COUNT(*) FROM tests')
        test_count = cursor.fetchone()[0]
        
        if test_count == 0 and teacher:
            # Создаем пример теста для преподавателя teacher
            cursor.execute('''
                INSERT INTO tests (title, description, teacher_id, target_groups)
                VALUES (?, ?, ?, ?)
            ''', ("Пример теста", "Это демонстрационный тест для проверки системы", teacher['id'], "1,2,3"))
            test_id = cursor.lastrowid
            print(f"  Добавлен пример теста (ID: {test_id})")
            
            # Вопрос 1
            cursor.execute('''
                INSERT INTO questions (test_id, question_text, points)
                VALUES (?, ?, ?)
            ''', (test_id, "Сколько будет 2 + 2?", 1))
            q1_id = cursor.lastrowid
            
            answers_q1 = [
                ("3", 0),
                ("4", 1),
                ("5", 0)
            ]
            for answer_text, is_correct in answers_q1:
                cursor.execute('''
                    INSERT INTO answers (question_id, answer_text, is_correct)
                    VALUES (?, ?, ?)
                ''', (q1_id, answer_text, is_correct))
            
            # Вопрос 2
            cursor.execute('''
                INSERT INTO questions (test_id, question_text, points)
                VALUES (?, ?, ?)
            ''', (test_id, "Сколько будет 3 * 3?", 1))
            q2_id = cursor.lastrowid
            
            answers_q2 = [
                ("6", 0),
                ("9", 1),
                ("12", 0)
            ]
            for answer_text, is_correct in answers_q2:
                cursor.execute('''
                    INSERT INTO answers (question_id, answer_text, is_correct)
                    VALUES (?, ?, ?)
                ''', (q2_id, answer_text, is_correct))
            
            print("  Пример теста успешно создан")

db = Database()