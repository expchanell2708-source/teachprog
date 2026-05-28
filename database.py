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

            # Пользователи (больше нет роли teacher)
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

            # Тесты (теперь teacher_id не нужен, используем created_by)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    created_by INTEGER NOT NULL,
                    target_groups TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
            ''')

            # Вопросы теста (добавлена колонка question_type)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_id INTEGER NOT NULL,
                    question_text TEXT NOT NULL,
                    question_type TEXT DEFAULT 'single',
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

            # Добавляем тестовых пользователей (admin, student)
            self._add_test_users(cursor)

    def _add_test_users(self, cursor):
        """Добавление тестовых пользователей"""
        users = [
            ("admin", "admin123", "Системный администратор", "admin", None),
            ("TatyanaMM", "Tatyana_Mihailovna123", "Татьяна Михайловна", "admin", None),
            #Группа 1
            ("student", "student123", "Баров Данила Михайлович", "student", "1"),
            ("student1", "student123", "Петров Петр Петрович", "student", "2"),
            ("student2", "student123", "Сидорова Анна Сергеевна", "student", "3"),
            ("BazhinaVS", "Bazhina_Victoria", "Бажина Виктория Сергеевна", "student", "1"),
            ("BalobanovYV", "BalobanovYaroslav", "Балобанов Ярослав Владимирович", "student", "1"),
            ("BalobanovaVD", "BalobanovaValeriya", "Балобанова Валерия Денисовна", "student", "1"),
            ("BondarevaEM", "BondarevaEkaterina", "Бондарева Екатерина Максимовна", "student", "1"),
            ("VagizovNI", "VagizovNiyaz", "Вагизов Нияз Ильгизович", "student", "1"),
            ("GadrshinLM", "GadrshinLenar", "Гадршин Ленар Маратович", "student", "1"),
            ("GruzdevaAS", "GrusdevaAnna", "Груздева Анна Сергеевна", "student", "1"),
            ("Dmitriev-LepehinFE", "FeliksEvgenevich", "Дмитриев-Лепихин Феликс Евгеньевич", "student", "1"),
            ("DonaurovAE", "DonaurovAndrei", "Донауров Андрей Евгеньевич", "student", "1"),
            ("ZaharovaTA", "ZaharovaTaisia", "Захарова Таисия Александровна", "student", "1"),
            # Группа 2
            ("IvanovDD", "IvanovDanil", "Иванов Данил Дмитриевич", "student", "2"),
            ("IkonnkiovLM", "IkonnikovLev", "Иконников Лев Михайлович", "student", "2"),
            ("KankasovKE", "KankasovKonstantin", "Канкасов Константин Эдуардович", "student", "2"),
            ("KozeevRO", "KozeevRoman", "Козеев Роман Олегович", "student", "2"),
            ("KostinaVD", "KostinaValeriya", "Костина Валерия Дмитриевна", "student", "2"),
            ("KuznecovIS", "KuznecovIvan", "Кузнецов Иван Сергеевич", "student", "2"),
            ("MarkovaOA", "VarkovaOlga", "Маркова Ольга Алексеевна", "student", "2"),
            ("MihalevaAO", "MihalevaAnastasia", "Михалева Анастасия Олеговна", "student", "2"),
            ("MicevichPA", "MicevichPolina", "Мицевич Полина Александровна", "student", "2"),
            ("MormishevAA", "MormishevAleksandr", "Мормышев Александр Александрович", "student", "2"),
            # Группа 3
            ("MuhametzyanovTF", "MuhametzyanovTimur", "Мухаметзянов Тимур Фанисович", "student", "3"),
            ("OnohinUA", "OnohinUryi", "Онохин Юрий Алексеевич", "student", "3"),
            ("PotaninaAN", "PotaninaAnastsia", "Потанина Анастасия Николаевна", "student", "3"),
            ("SazhinPA", "SazhinPavel", "Сажин Павел Александрович", "student", "3"),
            ("SafiullinaSE", "SafiullinaSofia", "Сафиуллина Софья Эдуардовна", "student", "3"),
            ("SigaevaPP", "SigaevaPolimna", "Сигаева Полина Павловна", "student", "3"),
            ("TerehinaDM", "TerehinaDiana", "Терехина Дана Михайловна", "student", "3"),
            ("ChadaevaSS", "ChadaevsCofia", "Чадаева Софья Сергеевна", "student", "3"),
            ("ShaggievTR", "ShagievTimur", "Шагиев Тимур Рафаэлевич", "student", "3"),
            
        ]

        for username, password, full_name, role, group_name in users:
            hashed = hashlib.sha256(password.encode()).hexdigest()
            try:
                cursor.execute('''
                    INSERT INTO users (username, password, full_name, role, group_name)
                    VALUES (?, ?, ?, ?, ?)
                ''', (username, hashed, full_name, role, group_name))
            except sqlite3.IntegrityError:
                pass

        # Создаём пример теста (если нет тестов)
        cursor.execute('SELECT COUNT(*) FROM tests')
        test_count = cursor.fetchone()[0]

        if test_count == 0:
            cursor.execute('SELECT id FROM users WHERE username="admin"')
            admin = cursor.fetchone()
            if admin:
                cursor.execute('''
                    INSERT INTO tests (title, description, created_by, target_groups)
                    VALUES (?, ?, ?, ?)
                ''', ("Пример теста", "Демонстрационный тест для проверки системы", admin['id'], "1,2,3"))
                test_id = cursor.lastrowid

                # Вопрос 1: Одиночный выбор
                cursor.execute('''
                    INSERT INTO questions (test_id, question_text, question_type, points)
                    VALUES (?, ?, ?, ?)
                ''', (test_id, "Сколько будет 2 + 2?", "single", 1))
                q1_id = cursor.lastrowid
                for ans, correct in [("3", 0), ("4", 1), ("5", 0)]:
                    cursor.execute('INSERT INTO answers (question_id, answer_text, is_correct) VALUES (?, ?, ?)',
                                   (q1_id, ans, correct))

                # Вопрос 2: Одиночный выбор
                cursor.execute('''
                    INSERT INTO questions (test_id, question_text, question_type, points)
                    VALUES (?, ?, ?, ?)
                ''', (test_id, "Сколько будет 3 * 3?", "single", 1))
                q2_id = cursor.lastrowid
                for ans, correct in [("6", 0), ("9", 1), ("12", 0)]:
                    cursor.execute('INSERT INTO answers (question_id, answer_text, is_correct) VALUES (?, ?, ?)',
                                   (q2_id, ans, correct))

                # Вопрос 3: Свой ответ (open)
                cursor.execute('''
                    INSERT INTO questions (test_id, question_text, question_type, points)
                    VALUES (?, ?, ?, ?)
                ''', (test_id, "Как называется язык программирования, на котором написана эта система?", "open", 2))
                q3_id = cursor.lastrowid
                cursor.execute('''
                    INSERT INTO answers (question_id, answer_text, is_correct)
                    VALUES (?, ?, ?)
                ''', (q3_id, "Python", 1))

db = Database()