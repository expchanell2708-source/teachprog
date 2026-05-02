from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from config import Config
from database import db
from auth import login_required, role_required, get_current_user
import sqlite3

app = Flask(__name__)
app.config.from_object(Config)

# Инициализация базы данных
db.init_db()

# ==================== АВТОРИЗАЦИЯ ====================

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username=?', (username,))
            user = cursor.fetchone()
            
            if user:
                import hashlib
                hashed = hashlib.sha256(password.encode()).hexdigest()
                if user['password'] == hashed:
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['full_name'] = user['full_name']
                    session['role'] = user['role']
                    session['group_name'] = user['group_name']
                    return redirect(url_for('dashboard'))
        
        return render_template('login.html', error="Неверное имя пользователя или пароль")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()
    
    if user['role'] == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif user['role'] == 'teacher':
        return redirect(url_for('teacher_tests'))
    elif user['role'] == 'student':
        return redirect(url_for('student_tests'))
    else:
        return render_template('dashboard.html', role=user['role'], full_name=user['full_name'])

# ==================== ПРЕПОДАВАТЕЛЬ ====================

@app.route('/teacher/tests')
@login_required
@role_required('teacher')
def teacher_tests():
    """Список тестов преподавателя"""
    user = get_current_user()
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.*, 
                   COUNT(DISTINCT q.id) as questions_count,
                   COUNT(DISTINCT tr.id) as attempts_count
            FROM tests t
            LEFT JOIN questions q ON t.id = q.test_id
            LEFT JOIN test_results tr ON t.id = tr.test_id
            WHERE t.teacher_id = ?
            GROUP BY t.id
            ORDER BY t.created_at DESC
        ''', (user['id'],))
        tests = cursor.fetchall()
    
    return render_template('teacher/tests_list.html', tests=tests)

@app.route('/teacher/create_test', methods=['GET', 'POST'])
@login_required
@role_required('teacher')
def create_test():
    """Создание нового теста"""
    user = get_current_user()
    
    # Получаем группы преподавателя
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT group_name FROM teacher_groups WHERE teacher_id=?', (user['id'],))
        teacher_groups = [row['group_name'] for row in cursor.fetchall()]
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        target_groups = ','.join(request.form.getlist('target_groups'))
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Создаем тест с указанием целевых групп
            cursor.execute('''
                INSERT INTO tests (title, description, teacher_id, target_groups)
                VALUES (?, ?, ?, ?)
            ''', (title, description, user['id'], target_groups))
            test_id = cursor.lastrowid
            
            # Получаем все данные формы
            form_data = request.form
            
            # Собираем вопросы
            questions_text = form_data.getlist('question_text[]')
            points_list = form_data.getlist('points[]')
            
            # Для каждого вопроса
            for idx, question_text in enumerate(questions_text):
                if not question_text:
                    continue
                
                # Получаем баллы
                points = points_list[idx] if idx < len(points_list) else 1
                
                # Создаем вопрос
                cursor.execute('''
                    INSERT INTO questions (test_id, question_text, points)
                    VALUES (?, ?, ?)
                ''', (test_id, question_text, points))
                question_id = cursor.lastrowid
                
                # Получаем ответы для этого вопроса
                answer_key = f'answers_{idx}[]'
                correct_key = f'correct_{idx}[]'
                
                answers = form_data.getlist(answer_key)
                correct_answers = form_data.getlist(correct_key)
                
                # Добавляем варианты ответов
                for ans_idx, answer_text in enumerate(answers):
                    if answer_text:
                        is_correct = 1 if str(ans_idx) in correct_answers else 0
                        
                        cursor.execute('''
                            INSERT INTO answers (question_id, answer_text, is_correct)
                            VALUES (?, ?, ?)
                        ''', (question_id, answer_text, is_correct))
        
        return redirect(url_for('teacher_tests'))
    
    return render_template('teacher/create_test.html', teacher_groups=teacher_groups)

@app.route('/teacher/groups')
@login_required
@role_required('teacher')
def teacher_groups():
    """Просмотр групп преподавателя (только чтение)"""
    user = get_current_user()
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Получаем текущие группы преподавателя
        cursor.execute('SELECT group_name FROM teacher_groups WHERE teacher_id=?', (user['id'],))
        current_groups = [row['group_name'] for row in cursor.fetchall()]
    
    return render_template('teacher/groups.html', current_groups=current_groups)

@app.route('/teacher/test/<int:test_id>')
@login_required
@role_required('teacher')
def test_details(test_id):
    """Просмотр теста"""
    user = get_current_user()
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Проверяем, что тест принадлежит преподавателю
        cursor.execute('SELECT * FROM tests WHERE id=? AND teacher_id=?', (test_id, user['id']))
        test = cursor.fetchone()
        
        if not test:
            return "Тест не найден", 404
        
        # Получаем вопросы с ответами
        cursor.execute('SELECT * FROM questions WHERE test_id=?', (test_id,))
        questions = cursor.fetchall()
        
        questions_with_answers = []
        for q in questions:
            cursor.execute('SELECT * FROM answers WHERE question_id=?', (q['id'],))
            answers = cursor.fetchall()
            questions_with_answers.append({
                'id': q['id'],
                'text': q['question_text'],
                'points': q['points'],
                'answers': answers
            })
        
        return render_template('teacher/test_details.html', test=test, questions=questions_with_answers)

@app.route('/teacher/test/<int:test_id>/results')
@login_required
@role_required('teacher')
def test_results(test_id):
    """Результаты теста"""
    user = get_current_user()
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Проверяем, что тест принадлежит преподавателю
        cursor.execute('SELECT * FROM tests WHERE id=? AND teacher_id=?', (test_id, user['id']))
        test = cursor.fetchone()
        
        if not test:
            return "Тест не найден", 404
        
        # Получаем результаты всех студентов
        cursor.execute('''
            SELECT tr.*, u.full_name, u.username, u.group_name
            FROM test_results tr
            JOIN users u ON tr.student_id = u.id
            WHERE tr.test_id = ?
            ORDER BY tr.percentage DESC
        ''', (test_id,))
        results = cursor.fetchall()
        
        # Статистика по тесту
        if results:
            avg_percentage = sum(r['percentage'] for r in results) / len(results)
            passed = sum(1 for r in results if r['percentage'] >= 60)
            total = len(results)
        else:
            avg_percentage = 0
            passed = 0
            total = 0
    
    return render_template('teacher/test_results.html', 
                         test=test, 
                         results=results,
                         avg_percentage=round(avg_percentage, 1),
                         passed=passed,
                         total=total)

@app.route('/teacher/result/<int:result_id>')
@login_required
@role_required('teacher')
def student_result_detail(result_id):
    """Детальный результат студента"""
    user = get_current_user()
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT tr.*, u.full_name, u.username, t.title as test_title
            FROM test_results tr
            JOIN users u ON tr.student_id = u.id
            JOIN tests t ON tr.test_id = t.id
            WHERE tr.id = ? AND t.teacher_id = ?
        ''', (result_id, user['id']))
        result = cursor.fetchone()
        
        if not result:
            return "Результат не найден", 404
        
        # Получаем детальные ответы
        cursor.execute('''
            SELECT sa.*, q.question_text, q.points, a.answer_text
            FROM student_answers sa
            JOIN questions q ON sa.question_id = q.id
            LEFT JOIN answers a ON sa.answer_id = a.id
            WHERE sa.result_id = ?
        ''', (result_id,))
        answers = cursor.fetchall()
        
        # Получаем правильные ответы для сравнения
        cursor.execute('''
            SELECT q.id as question_id, a.answer_text
            FROM questions q
            JOIN answers a ON q.id = a.question_id
            WHERE q.test_id = ? AND a.is_correct = 1
        ''', (result['test_id'],))
        correct_answers = cursor.fetchall()
        
        # Группируем правильные ответы по вопросам
        correct_by_question = {}
        for ca in correct_answers:
            if ca['question_id'] not in correct_by_question:
                correct_by_question[ca['question_id']] = []
            correct_by_question[ca['question_id']].append(ca['answer_text'])
    
    return render_template('teacher/student_result.html', 
                         result=result, 
                         answers=answers,
                         correct_by_question=correct_by_question)

@app.route('/teacher/delete_test/<int:test_id>', methods=['POST'])
@login_required
@role_required('teacher')
def delete_test(test_id):
    """Удаление теста"""
    user = get_current_user()
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Проверяем, что тест принадлежит преподавателю
            cursor.execute('SELECT id FROM tests WHERE id=? AND teacher_id=?', (test_id, user['id']))
            test = cursor.fetchone()
            
            if not test:
                return jsonify({'success': False, 'error': 'Тест не найден'}), 404
            
            # Удаляем тест (каскадное удаление удалит вопросы, ответы и результаты)
            cursor.execute('DELETE FROM tests WHERE id=?', (test_id,))
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== СТУДЕНТ ====================

@app.route('/student/tests')
@login_required
@role_required('student')
def student_tests():
    """Доступные тесты для студента"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Получаем группу студента
        cursor.execute('SELECT group_name FROM users WHERE id=?', (session['user_id'],))
        student = cursor.fetchone()
        student_group = student['group_name'] if student else None
        
        # Получаем тесты, доступные для группы студента
        if student_group:
            cursor.execute('''
                SELECT t.*, u.full_name as teacher_name,
                       CASE WHEN tr.id IS NOT NULL THEN 1 ELSE 0 END as completed,
                       tr.percentage as last_score
                FROM tests t
                JOIN users u ON t.teacher_id = u.id
                LEFT JOIN test_results tr ON t.id = tr.test_id AND tr.student_id = ?
                WHERE t.is_active = 1 
                AND (
                    t.target_groups IS NULL 
                    OR t.target_groups = '' 
                    OR t.target_groups LIKE ? 
                    OR t.target_groups LIKE ? 
                    OR t.target_groups LIKE ?
                )
                ORDER BY t.created_at DESC
            ''', (
                session['user_id'], 
                f'%{student_group}%',
                f'{student_group},%',
                f'%,{student_group}%'
            ))
        else:
            # Если у студента нет группы, показываем только тесты без ограничений
            cursor.execute('''
                SELECT t.*, u.full_name as teacher_name,
                       CASE WHEN tr.id IS NOT NULL THEN 1 ELSE 0 END as completed,
                       tr.percentage as last_score
                FROM tests t
                JOIN users u ON t.teacher_id = u.id
                LEFT JOIN test_results tr ON t.id = tr.test_id AND tr.student_id = ?
                WHERE t.is_active = 1 
                AND (t.target_groups IS NULL OR t.target_groups = '')
                ORDER BY t.created_at DESC
            ''', (session['user_id'],))
        
        tests = cursor.fetchall()
    
    return render_template('student/available_tests.html', tests=tests)

@app.route('/student/take_test/<int:test_id>')
@login_required
@role_required('student')
def take_test(test_id):
    """Страница прохождения теста"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Проверяем, не проходил ли студент этот тест
        cursor.execute('''
            SELECT id FROM test_results 
            WHERE test_id = ? AND student_id = ?
        ''', (test_id, session['user_id']))
        existing = cursor.fetchone()
        
        if existing:
            return redirect(url_for('test_result', result_id=existing['id']))
        
        # Получаем тест и вопросы
        cursor.execute('SELECT * FROM tests WHERE id=? AND is_active=1', (test_id,))
        test = cursor.fetchone()
        
        if not test:
            return "Тест не найден", 404
        
        cursor.execute('''
            SELECT q.*, a.id as answer_id, a.answer_text, a.is_correct
            FROM questions q
            LEFT JOIN answers a ON q.id = a.question_id
            WHERE q.test_id = ?
            ORDER BY q.id
        ''', (test_id,))
        
        # Группируем вопросы
        questions = {}
        for row in cursor.fetchall():
            q_id = row['id']
            if q_id not in questions:
                questions[q_id] = {
                    'id': q_id,
                    'text': row['question_text'],
                    'points': row['points'],
                    'answers': []
                }
            if row['answer_id']:
                questions[q_id]['answers'].append({
                    'id': row['answer_id'],
                    'text': row['answer_text']
                })
    
    return render_template('student/take_test.html', test=test, questions=questions.values())

@app.route('/student/submit_test/<int:test_id>', methods=['POST'])
@login_required
@role_required('student')
def submit_test(test_id):
    """Сохранение результатов теста"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Получаем все вопросы и их максимальные баллы
        cursor.execute('SELECT id, points FROM questions WHERE test_id=?', (test_id,))
        questions = cursor.fetchall()
        
        max_score = sum(q['points'] for q in questions)
        user_score = 0
        
        # Создаем запись о результате
        cursor.execute('''
            INSERT INTO test_results (test_id, student_id, score, max_score, percentage)
            VALUES (?, ?, ?, ?, ?)
        ''', (test_id, session['user_id'], 0, max_score, 0))
        result_id = cursor.lastrowid
        
        # Обрабатываем ответы на каждый вопрос
        for question in questions:
            q_id = question['id']
            points = question['points']
            
            # Получаем ответы пользователя
            user_answers = request.form.getlist(f'question_{q_id}')
            
            # Получаем правильные ответы
            cursor.execute('SELECT id FROM answers WHERE question_id=? AND is_correct=1', (q_id,))
            correct_answers = [a['id'] for a in cursor.fetchall()]
            
            # Проверяем правильность
            is_correct = False
            if len(correct_answers) == 1 and len(user_answers) == 1:
                is_correct = int(user_answers[0]) == correct_answers[0]
            elif len(correct_answers) > 1:
                user_set = set(int(a) for a in user_answers)
                correct_set = set(correct_answers)
                is_correct = user_set == correct_set
            
            if is_correct:
                user_score += points
            
            # Сохраняем каждый ответ
            for answer_id in user_answers:
                cursor.execute('''
                    INSERT INTO student_answers (result_id, question_id, answer_id, is_correct)
                    VALUES (?, ?, ?, ?)
                ''', (result_id, q_id, answer_id, is_correct))
        
        # Обновляем результат
        percentage = (user_score / max_score * 100) if max_score > 0 else 0
        cursor.execute('''
            UPDATE test_results 
            SET score=?, percentage=?
            WHERE id=?
        ''', (user_score, percentage, result_id))
    
    return redirect(url_for('test_result', result_id=result_id))

@app.route('/student/result/<int:result_id>')
@login_required
def test_result(result_id):
    """Просмотр результата теста"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT tr.*, t.title, t.description, u.full_name as teacher_name
            FROM test_results tr
            JOIN tests t ON tr.test_id = t.id
            JOIN users u ON t.teacher_id = u.id
            WHERE tr.id = ? AND tr.student_id = ?
        ''', (result_id, session['user_id']))
        result = cursor.fetchone()
        
        if not result:
            return "Результат не найден", 404
        
        # Получаем ответы с вопросами
        cursor.execute('''
            SELECT sa.*, q.question_text, q.points, a.answer_text
            FROM student_answers sa
            JOIN questions q ON sa.question_id = q.id
            LEFT JOIN answers a ON sa.answer_id = a.id
            WHERE sa.result_id = ?
        ''', (result_id,))
        answers = cursor.fetchall()
        
        # Группируем по вопросам
        questions_dict = {}
        for ans in answers:
            q_id = ans['question_id']
            if q_id not in questions_dict:
                questions_dict[q_id] = {
                    'text': ans['question_text'],
                    'points': ans['points'],
                    'answers': []
                }
            if ans['answer_text']:
                questions_dict[q_id]['answers'].append(ans['answer_text'])
        
        # Получаем правильные ответы
        cursor.execute('''
            SELECT q.id as question_id, a.answer_text
            FROM questions q
            JOIN answers a ON q.id = a.question_id
            WHERE q.test_id = ? AND a.is_correct = 1
        ''', (result['test_id'],))
        correct_answers = cursor.fetchall()
        
        correct_by_question = {}
        for ca in correct_answers:
            if ca['question_id'] not in correct_by_question:
                correct_by_question[ca['question_id']] = []
            correct_by_question[ca['question_id']].append(ca['answer_text'])
    
    return render_template('student/result.html', 
                         result=result, 
                         questions=questions_dict,
                         correct_by_question=correct_by_question)

# ==================== АДМИНИСТРАТОР ====================

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    """Панель управления администратора"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Общая статистика
        cursor.execute("SELECT COUNT(*) FROM users WHERE role='teacher'")
        teachers_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE role='student'")
        students_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tests")
        tests_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM test_results")
        results_count = cursor.fetchone()[0]
        
        # Последние созданные тесты
        cursor.execute('''
            SELECT t.*, u.full_name as teacher_name
            FROM tests t
            JOIN users u ON t.teacher_id = u.id
            ORDER BY t.created_at DESC
            LIMIT 5
        ''')
        recent_tests = cursor.fetchall()
        
        # Последние результаты
        cursor.execute('''
            SELECT tr.*, t.title, u.full_name as student_name
            FROM test_results tr
            JOIN tests t ON tr.test_id = t.id
            JOIN users u ON tr.student_id = u.id
            ORDER BY tr.completed_at DESC
            LIMIT 5
        ''')
        recent_results = cursor.fetchall()
        
        stats = {
            'teachers': teachers_count,
            'students': students_count,
            'tests': tests_count,
            'results': results_count
        }
    
    return render_template('admin/dashboard.html', 
                         stats=stats, 
                         recent_tests=recent_tests,
                         recent_results=recent_results)

@app.route('/admin/users')
@login_required
@role_required('admin')
def admin_users():
    """Управление пользователями"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Получаем всех пользователей
        cursor.execute('''
            SELECT id, username, full_name, role, group_name, created_at
            FROM users
            ORDER BY 
                CASE role 
                    WHEN 'admin' THEN 1
                    WHEN 'teacher' THEN 2
                    WHEN 'student' THEN 3
                END,
                created_at DESC
        ''')
        users = cursor.fetchall()
    
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/add', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_add_user():
    """Добавление нового пользователя"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        role = request.form.get('role')
        group_name = request.form.get('group_name', '')
        
        # Проверяем, не занят ли логин
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM users WHERE username=?', (username,))
            existing = cursor.fetchone()
            
            if existing:
                return render_template('admin/user_form.html', 
                                     error="Пользователь с таким логином уже существует")
            
            import hashlib
            hashed = hashlib.sha256(password.encode()).hexdigest()
            
            cursor.execute('''
                INSERT INTO users (username, password, full_name, role, group_name)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, hashed, full_name, role, group_name))
        
        return redirect(url_for('admin_users'))
    
    return render_template('admin/user_form.html')

@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_edit_user(user_id):
    """Редактирование пользователя"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        if request.method == 'POST':
            full_name = request.form.get('full_name')
            role = request.form.get('role')
            group_name = request.form.get('group_name', '')
            new_password = request.form.get('new_password', '')
            
            if new_password:
                import hashlib
                hashed = hashlib.sha256(new_password.encode()).hexdigest()
                cursor.execute('''
                    UPDATE users 
                    SET full_name=?, role=?, group_name=?, password=?
                    WHERE id=?
                ''', (full_name, role, group_name, hashed, user_id))
            else:
                cursor.execute('''
                    UPDATE users 
                    SET full_name=?, role=?, group_name=?
                    WHERE id=?
                ''', (full_name, role, group_name, user_id))
            
            return redirect(url_for('admin_users'))
        
        # GET запрос - показываем форму
        cursor.execute('SELECT * FROM users WHERE id=?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return "Пользователь не найден", 404
        
        return render_template('admin/user_form.html', user=user, edit_mode=True)

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_user(user_id):
    """Удаление пользователя"""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Проверяем, не пытается ли админ удалить самого себя
            if user_id == session['user_id']:
                return jsonify({'success': False, 'error': 'Нельзя удалить самого себя'}), 400
            
            # Проверяем существование пользователя
            cursor.execute('SELECT id, role, username FROM users WHERE id=?', (user_id,))
            user = cursor.fetchone()
            
            if not user:
                return jsonify({'success': False, 'error': 'Пользователь не найден'}), 404
            
            # Если это преподаватель, удаляем его группы
            if user['role'] == 'teacher':
                cursor.execute('DELETE FROM teacher_groups WHERE teacher_id=?', (user_id,))
            
            # Если это студент, удаляем его результаты тестов
            if user['role'] == 'student':
                # Получаем все результаты студента
                cursor.execute('SELECT id FROM test_results WHERE student_id=?', (user_id,))
                results = cursor.fetchall()
                
                # Удаляем детальные ответы для каждого результата
                for result in results:
                    cursor.execute('DELETE FROM student_answers WHERE result_id=?', (result['id'],))
                
                # Удаляем результаты тестов
                cursor.execute('DELETE FROM test_results WHERE student_id=?', (user_id,))
            
            # Удаляем пользователя
            cursor.execute('DELETE FROM users WHERE id=?', (user_id,))
            
            # Принудительно сохраняем изменения
            conn.commit()
            
            # Проверяем, что пользователь действительно удален
            cursor.execute('SELECT id FROM users WHERE id=?', (user_id,))
            check = cursor.fetchone()
            
            if not check:
                return jsonify({'success': True, 'message': f'Пользователь {user["username"]} успешно удален'})
            else:
                return jsonify({'success': False, 'error': 'Не удалось удалить пользователя'}), 500
            
    except Exception as e:
        print(f"Ошибка при удалении пользователя: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/stats')
@login_required
@role_required('admin')
def admin_stats():
    """Расширенная статистика"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Статистика по ролям
        cursor.execute('''
            SELECT role, COUNT(*) as count
            FROM users
            GROUP BY role
        ''')
        role_stats = cursor.fetchall()
        
        # Статистика по тестам
        cursor.execute('''
            SELECT 
                COUNT(*) as total_tests,
                AVG(questions_count) as avg_questions
            FROM (
                SELECT t.id, COUNT(q.id) as questions_count
                FROM tests t
                LEFT JOIN questions q ON t.id = q.test_id
                GROUP BY t.id
            )
        ''')
        test_stats = cursor.fetchone()
        
        # Топ преподавателей по количеству тестов
        cursor.execute('''
            SELECT u.full_name, COUNT(t.id) as test_count
            FROM users u
            LEFT JOIN tests t ON u.id = t.teacher_id
            WHERE u.role = 'teacher'
            GROUP BY u.id
            ORDER BY test_count DESC
            LIMIT 5
        ''')
        top_teachers = cursor.fetchall()
        
        # Топ студентов по результатам
        cursor.execute('''
            SELECT u.full_name, AVG(tr.percentage) as avg_score, COUNT(tr.id) as tests_passed
            FROM users u
            JOIN test_results tr ON u.id = tr.student_id
            GROUP BY u.id
            ORDER BY avg_score DESC
            LIMIT 5
        ''')
        top_students = cursor.fetchall()
        
        # Динамика регистрации пользователей по дням
        cursor.execute('''
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM users
            WHERE created_at >= DATE('now', '-30 days')
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        ''')
        registration_stats = cursor.fetchall()
    
    return render_template('admin/stats.html',
                         role_stats=role_stats,
                         test_stats=test_stats,
                         top_teachers=top_teachers,
                         top_students=top_students,
                         registration_stats=registration_stats)

@app.route('/admin/teacher_groups/<int:teacher_id>', methods=['GET'])
@login_required
@role_required('admin')
def get_teacher_groups(teacher_id):
    """Получить группы преподавателя"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT group_name FROM teacher_groups WHERE teacher_id=?', (teacher_id,))
        groups = [row['group_name'] for row in cursor.fetchall()]
        
        return jsonify({'groups': groups})

@app.route('/admin/teacher_groups/<int:teacher_id>', methods=['POST'])
@login_required
@role_required('admin')
def set_teacher_groups(teacher_id):
    """Установить группы преподавателя"""
    data = request.get_json()
    groups = data.get('groups', [])
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Удаляем старые группы
        cursor.execute('DELETE FROM teacher_groups WHERE teacher_id=?', (teacher_id,))
        
        # Добавляем новые группы
        for group in groups:
            if group.strip():
                try:
                    cursor.execute('''
                        INSERT INTO teacher_groups (teacher_id, group_name)
                        VALUES (?, ?)
                    ''', (teacher_id, group.strip()))
                except sqlite3.IntegrityError:
                    pass
        
        return jsonify({'success': True})

@app.route('/admin/all_groups')
@login_required
@role_required('admin')
def get_all_groups():
    """Получить все существующие группы студентов"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT group_name 
            FROM users 
            WHERE role='student' AND group_name IS NOT NULL AND group_name != ''
            ORDER BY group_name
        ''')
        groups = [row['group_name'] for row in cursor.fetchall()]
        
        return jsonify({'groups': groups})
    
@app.route('/admin/users/count')
@login_required
@role_required('admin')
def get_user_counts():
    """Получить количество пользователей по ролям"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE role='teacher'")
        teachers = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE role='student'")
        students = cursor.fetchone()[0]
        
        return jsonify({'success': True, 'teachers': teachers, 'students': students})

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'], host=app.config['HOST'], port=app.config['PORT'])