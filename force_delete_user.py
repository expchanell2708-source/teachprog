# force_delete_user.py
import sqlite3
import sys

def force_delete_user(username):
    conn = sqlite3.connect('knowledge_test.db')
    cursor = conn.cursor()
    
    # Получаем ID пользователя
    cursor.execute("SELECT id, full_name, role FROM users WHERE username=?", (username,))
    user = cursor.fetchone()
    
    if user:
        user_id = user[0]
        full_name = user[1]
        role = user[2]
        
        print(f"Найден пользователь: {username} ({full_name}) - {role}")
        confirm = input(f"Удалить этого пользователя? (y/n): ")
        
        if confirm.lower() == 'y':
            # Удаляем группы преподавателя
            if role == 'teacher':
                cursor.execute("DELETE FROM teacher_groups WHERE teacher_id=?", (user_id,))
                print(f"  ✓ Удалены группы преподавателя")
            
            # Удаляем результаты тестов для студента
            if role == 'student':
                cursor.execute("SELECT id FROM test_results WHERE student_id=?", (user_id,))
                results = cursor.fetchall()
                for result in results:
                    cursor.execute("DELETE FROM student_answers WHERE result_id=?", (result[0],))
                cursor.execute("DELETE FROM test_results WHERE student_id=?", (user_id,))
                print(f"  ✓ Удалены результаты тестов")
            
            # Удаляем пользователя
            cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
            conn.commit()
            print(f"✓ Пользователь {username} успешно удален!")
        else:
            print("Операция отменена")
    else:
        print(f"✗ Пользователь {username} не найден")
    
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Если передан аргумент командной строки
        username = sys.argv[1]
        force_delete_user(username)
    else:
        # Если аргумент не передан, запрашиваем ввод
        username = input("Введите логин пользователя для удаления: ")
        force_delete_user(username)