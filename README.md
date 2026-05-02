# teachprog
Создайте файл .env в корне проекта, если его нет, со следующим содержимым:

FLASK_APP=app.py
FLASK_DEBUG=True
SECRET_KEY=your-secret-key-here
DATABASE_PATH=knowledge_test.db
HOST=127.0.0.1
PORT=5000

Пропишите эти команды в консоли VSCode по очереди:

1. python --version (Должно вывести: Python 3.11.x или выше)
2. python -m venv venv
3. venv\Scripts\activate.bat (Активация виртуального окружения) ИЛИ
Прописать в Windows PowerShell venv\Scripts\Activate.ps1
4. pip install -r requirements.txt
5.(Запуск через python) python app.py ИЛИ (запуск через Flask) flask run

В РЕЗУЛЬТАТЕ БУДЕТ:
* Serving Flask app 'app'
* Debug mode: on
* Running on http://127.0.0.1:5000 (Вставить адрес в браузер)
Press CTRL+C to quit
* Restarting with stat
* Debugger is active!

ДЛЯ ДЕАКВТИАЦИИ НАЖМИТЕ КЛАВИШИ CTRL+C

ВОЗМОЖНЫЕ ОШИБКИ И ИХ РЕШЕНИЯ

Ошибка: "Python was not found"
Решение: Python не установлен или не добавлен в PATH. Установите Python заново, отметив галочку "Add Python to PATH".

Ошибка: "No module named flask"
Решение: Зависимости не установлены. 
Выполните(консоль):
pip install flask python-dotenv

Ошибка: "No such column: target_groups"
Решение: Удалите старую базу данных и создайте новую(консоль):
del knowledge_test.db
python app.py

Ошибка: "TemplateNotFound"
Решение: Проверьте структуру папки templates. Все шаблоны должны находиться в правильных подпапках: admin/, teacher/, student/.

Ошибка: "Port 5000 already in use"
Решение: Порт 5000 занят другим приложением. Измените порт в файле .env:
PORT=5001
Затем перезапустите приложение.

Ошибка активации виртуального окружения в PowerShell
Решение: Запустите PowerShell от имени администратора и выполните(Powershell):
Set-ExecutionPolicy RemoteSigned
Затем подтвердите, нажав Y.

Или просто используйте Command Prompt (cmd) вместо PowerShell.
