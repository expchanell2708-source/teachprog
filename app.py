from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from config import Config
from database import db
from auth import login_required, role_required, get_current_user
import sqlite3

app = Flask(__name__)
app.config.from_object(Config)

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
    elif user['role'] == 'student':
        return redirect(url_for('student_tests'))
    else:
        return render_template('dashboard.html', role=user['role'], full_name=user['full_name'])

# ==================== АДМИНИСТРАТОР (весь функционал учителя здесь) ====================

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE role='student'")
        students_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM tests")
        tests_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM test_results")
        results_count = cursor.fetchone()[0]

        cursor.execute('''
            SELECT t.*, u.full_name as creator_name
            FROM tests t
            JOIN users u ON t.created_by = u.id
            ORDER BY t.created_at DESC
            LIMIT 5
        ''')
        recent_tests = cursor.fetchall()

        stats = {
            'students': students_count,
            'tests': tests_count,
            'results': results_count
        }

    return render_template('admin/dashboard.html', stats=stats, recent_tests=recent_tests)

@app.route('/admin/tests')
@login_required
@role_required('admin')
def admin_tests():
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.*, 
                   COUNT(DISTINCT q.id) as questions_count,
                   COUNT(DISTINCT tr.id) as attempts_count
            FROM tests t
            LEFT JOIN questions q ON t.id = q.test_id
            LEFT JOIN test_results tr ON t.id = tr.test_id
            GROUP BY t.id
            ORDER BY t.created_at DESC
        ''')
        tests = cursor.fetchall()
    return render_template('admin/tests_list.html', tests=tests)

@app.route('/admin/create_test', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_create_test():
    user = get_current_user()

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        target_groups = ','.join(request.form.getlist('target_groups'))

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tests (title, description, created_by, target_groups)
                VALUES (?, ?, ?, ?)
            ''', (title, description, user['id'], target_groups))
            test_id = cursor.lastrowid

            form_data = request.form
            questions_text = form_data.getlist('question_text[]')
            points_list = form_data.getlist('points[]')

            for idx, question_text in enumerate(questions_text):
                if not question_text:
                    continue
                points = points_list[idx] if idx < len(points_list) else 1

                cursor.execute('''
                    INSERT INTO questions (test_id, question_text, points)
                    VALUES (?, ?, ?)
                ''', (test_id, question_text, points))
                question_id = cursor.lastrowid

                answer_key = f'answers_{idx}[]'
                correct_key = f'correct_{idx}[]'
                answers = form_data.getlist(answer_key)
                correct_answers = form_data.getlist(correct_key)

                for ans_idx, answer_text in enumerate(answers):
                    if answer_text:
                        is_correct = 1 if str(ans_idx) in correct_answers else 0
                        cursor.execute('''
                            INSERT INTO answers (question_id, answer_text, is_correct)
                            VALUES (?, ?, ?)
                        ''', (question_id, answer_text, is_correct))

        return redirect(url_for('admin_tests'))

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT group_name FROM users WHERE role="student" AND group_name IS NOT NULL')
        groups = [row['group_name'] for row in cursor.fetchall()]
    return render_template('admin/create_test.html', groups=groups)

@app.route('/admin/test/<int:test_id>')
@login_required
@role_required('admin')
def admin_test_details(test_id):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tests WHERE id=?', (test_id,))
        test = cursor.fetchone()
        if not test:
            return "Тест не найден", 404

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
    return render_template('admin/test_details.html', test=test, questions=questions_with_answers)

@app.route('/admin/test/<int:test_id>/results')
@login_required
@role_required('admin')
def admin_test_results(test_id):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tests WHERE id=?', (test_id,))
        test = cursor.fetchone()
        if not test:
            return "Тест не найден", 404

        cursor.execute('''
            SELECT tr.*, u.full_name, u.username, u.group_name
            FROM test_results tr
            JOIN users u ON tr.student_id = u.id
            WHERE tr.test_id = ?
            ORDER BY tr.percentage DESC
        ''', (test_id,))
        results = cursor.fetchall()

        if results:
            avg_percentage = sum(r['percentage'] for r in results) / len(results)
            passed = sum(1 for r in results if r['percentage'] >= 60)
            total = len(results)
        else:
            avg_percentage = 0
            passed = 0
            total = 0

    return render_template('admin/test_results.html',
                         test=test,
                         results=results,
                         avg_percentage=round(avg_percentage, 1),
                         passed=passed,
                         total=total)

@app.route('/admin/result/<int:result_id>')
@login_required
@role_required('admin')
def admin_student_result_detail(result_id):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT tr.*, u.full_name, u.username, t.title as test_title
            FROM test_results tr
            JOIN users u ON tr.student_id = u.id
            JOIN tests t ON tr.test_id = t.id
            WHERE tr.id = ?
        ''', (result_id,))
        result = cursor.fetchone()
        if not result:
            return "Результат не найден", 404

        cursor.execute('''
            SELECT sa.*, q.question_text, q.points, a.answer_text
            FROM student_answers sa
            JOIN questions q ON sa.question_id = q.id
            LEFT JOIN answers a ON sa.answer_id = a.id
            WHERE sa.result_id = ?
        ''', (result_id,))
        answers = cursor.fetchall()

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

    return render_template('admin/student_result.html',
                         result=result,
                         answers=answers,
                         correct_by_question=correct_by_question)

@app.route('/admin/delete_test/<int:test_id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_test(test_id):
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM tests WHERE id=?', (test_id,))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/users')
@login_required
@role_required('admin')
def admin_users():
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, full_name, role, group_name, created_at
            FROM users
            ORDER BY created_at DESC
        ''')
        users = cursor.fetchall()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/add', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_add_user():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        role = request.form.get('role')
        group_name = request.form.get('group_name', '')

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM users WHERE username=?', (username,))
            if cursor.fetchone():
                return render_template('admin/user_form.html', error="Пользователь уже существует")

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
                    UPDATE users SET full_name=?, role=?, group_name=?, password=?
                    WHERE id=?
                ''', (full_name, role, group_name, hashed, user_id))
            else:
                cursor.execute('''
                    UPDATE users SET full_name=?, role=?, group_name=?
                    WHERE id=?
                ''', (full_name, role, group_name, user_id))
            return redirect(url_for('admin_users'))

        cursor.execute('SELECT * FROM users WHERE id=?', (user_id,))
        user = cursor.fetchone()
    return render_template('admin/user_form.html', user=user, edit_mode=True)

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_user(user_id):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        if user_id == session['user_id']:
            return jsonify({'success': False, 'error': 'Нельзя удалить самого себя'}), 400

        cursor.execute('DELETE FROM teacher_groups WHERE teacher_id=?', (user_id,))
        cursor.execute('DELETE FROM test_results WHERE student_id=?', (user_id,))
        cursor.execute('DELETE FROM users WHERE id=?', (user_id,))
        return jsonify({'success': True})

# ==================== СТУДЕНТ ====================

@app.route('/student/tests')
@login_required
@role_required('student')
def student_tests():
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT group_name FROM users WHERE id=?', (session['user_id'],))
        student = cursor.fetchone()
        student_group = student['group_name'] if student else None

        if student_group:
            cursor.execute('''
                SELECT t.*, u.full_name as creator_name,
                       CASE WHEN tr.id IS NOT NULL THEN 1 ELSE 0 END as completed,
                       tr.percentage as last_score
                FROM tests t
                JOIN users u ON t.created_by = u.id
                LEFT JOIN test_results tr ON t.id = tr.test_id AND tr.student_id = ?
                WHERE t.is_active = 1
                AND (t.target_groups IS NULL OR t.target_groups = '' OR t.target_groups LIKE ?)
                ORDER BY t.created_at DESC
            ''', (session['user_id'], f'%{student_group}%'))
        else:
            cursor.execute('''
                SELECT t.*, u.full_name as creator_name,
                       CASE WHEN tr.id IS NOT NULL THEN 1 ELSE 0 END as completed,
                       tr.percentage as last_score
                FROM tests t
                JOIN users u ON t.created_by = u.id
                LEFT JOIN test_results tr ON t.id = tr.test_id AND tr.student_id = ?
                WHERE t.is_active = 1 AND (t.target_groups IS NULL OR t.target_groups = '')
                ORDER BY t.created_at DESC
            ''', (session['user_id'],))
        tests = cursor.fetchall()
    return render_template('student/available_tests.html', tests=tests)

@app.route('/student/take_test/<int:test_id>')
@login_required
@role_required('student')
def take_test(test_id):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM test_results WHERE test_id=? AND student_id=?',
                       (test_id, session['user_id']))
        if cursor.fetchone():
            return redirect(url_for('student_tests'))

        cursor.execute('SELECT * FROM tests WHERE id=? AND is_active=1', (test_id,))
        test = cursor.fetchone()
        if not test:
            return "Тест не найден", 404

        cursor.execute('''
            SELECT q.*, a.id as answer_id, a.answer_text
            FROM questions q
            LEFT JOIN answers a ON q.id = a.question_id
            WHERE q.test_id = ?
            ORDER BY q.id
        ''', (test_id,))
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
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, points FROM questions WHERE test_id=?', (test_id,))
        questions = cursor.fetchall()

        max_score = sum(q['points'] for q in questions)
        user_score = 0

        cursor.execute('''
            INSERT INTO test_results (test_id, student_id, score, max_score, percentage)
            VALUES (?, ?, ?, ?, ?)
        ''', (test_id, session['user_id'], 0, max_score, 0))
        result_id = cursor.lastrowid

        for question in questions:
            q_id = question['id']
            points = question['points']
            user_answers = request.form.getlist(f'question_{q_id}')

            cursor.execute('SELECT id FROM answers WHERE question_id=? AND is_correct=1', (q_id,))
            correct_answers = [a['id'] for a in cursor.fetchall()]

            is_correct = False
            if len(correct_answers) == 1 and len(user_answers) == 1:
                is_correct = int(user_answers[0]) == correct_answers[0]
            elif len(correct_answers) > 1:
                user_set = set(int(a) for a in user_answers)
                correct_set = set(correct_answers)
                is_correct = user_set == correct_set

            if is_correct:
                user_score += points

            for answer_id in user_answers:
                cursor.execute('''
                    INSERT INTO student_answers (result_id, question_id, answer_id, is_correct)
                    VALUES (?, ?, ?, ?)
                ''', (result_id, q_id, answer_id, is_correct))

        percentage = (user_score / max_score * 100) if max_score > 0 else 0
        cursor.execute('UPDATE test_results SET score=?, percentage=? WHERE id=?',
                       (user_score, percentage, result_id))

    return redirect(url_for('test_result', result_id=result_id))

@app.route('/student/result/<int:result_id>')
@login_required
def test_result(result_id):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT tr.*, t.title, t.description, u.full_name as creator_name
            FROM test_results tr
            JOIN tests t ON tr.test_id = t.id
            JOIN users u ON t.created_by = u.id
            WHERE tr.id = ? AND tr.student_id = ?
        ''', (result_id, session['user_id']))
        result = cursor.fetchone()
        if not result:
            return "Результат не найден", 404

        cursor.execute('''
            SELECT sa.*, q.question_text, q.points, a.answer_text
            FROM student_answers sa
            JOIN questions q ON sa.question_id = q.id
            LEFT JOIN answers a ON sa.answer_id = a.id
            WHERE sa.result_id = ?
        ''', (result_id,))
        answers = cursor.fetchall()

        questions_dict = {}
        for ans in answers:
            q_id = ans['question_id']
            if q_id not in questions_dict:
                questions_dict[q_id] = {
                    'text': ans['question_text'],
                    'points': ans['points'],
                    'answers': []
                }
            questions_dict[q_id]['answers'].append(ans['answer_text'])

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

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'], host=app.config['HOST'], port=app.config['PORT'])