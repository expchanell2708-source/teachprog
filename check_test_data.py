import sqlite3

def check_test_data():
    conn = sqlite3.connect('knowledge_test.db')
    cursor = conn.cursor()
    
    # Получаем все тесты
    cursor.execute("SELECT id, title FROM tests")
    tests = cursor.fetchall()
    
    for test in tests:
        print(f"\n{'='*50}")
        print(f"Тест: {test[1]} (ID: {test[0]})")
        print('='*50)
        
        # Получаем вопросы
        cursor.execute("SELECT id, question_text, points FROM questions WHERE test_id=?", (test[0],))
        questions = cursor.fetchall()
        
        for q in questions:
            print(f"\n  Вопрос: {q[1]} ({q[2]} баллов)")
            print(f"  ID вопроса: {q[0]}")
            
            # Получаем ответы
            cursor.execute("SELECT id, answer_text, is_correct FROM answers WHERE question_id=?", (q[0],))
            answers = cursor.fetchall()
            
            if answers:
                print("  Варианты ответов:")
                for a in answers:
                    correct_mark = "✓" if a[2] else "✗"
                    print(f"    {correct_mark} {a[1]}")
            else:
                print("  ⚠️ НЕТ ВАРИАНТОВ ОТВЕТОВ!")

if __name__ == "__main__":
    check_test_data()