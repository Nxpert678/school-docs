from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'school_secret_key_2026'

# ========== НАСТРОЙКА БАЗЫ ДАННЫХ ==========
# На Render используем /var/data, на локальном компьютере - текущую папку
DATA_DIR = '/var/data' if os.path.exists('/var/data') else '.'
DATABASE = os.path.join(DATA_DIR, 'school.db')


def get_db():
    """Возвращает соединение с базой данных"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Создаёт таблицы и начальных пользователей при первом запуске"""
    conn = get_db()
    c = conn.cursor()

    # Таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  role TEXT NOT NULL,
                  class TEXT,
                  login TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL)''')

    # Таблица заявлений
    c.execute('''CREATE TABLE IF NOT EXISTS applications
                 (number TEXT PRIMARY KEY,
                  user_id INTEGER NOT NULL,
                  user_name TEXT NOT NULL,
                  type TEXT NOT NULL,
                  date TEXT NOT NULL,
                  reason TEXT NOT NULL,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  reject_reason TEXT,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')

    # Таблица счётчика номеров
    c.execute('''CREATE TABLE IF NOT EXISTS counter
                 (id INTEGER PRIMARY KEY,
                  next INTEGER NOT NULL)''')

    # Добавляем счётчик, если его нет
    c.execute("SELECT * FROM counter WHERE id=1")
    if not c.fetchone():
        c.execute("INSERT INTO counter (id, next) VALUES (1, 1)")

    # Добавляем директора, если его нет
    c.execute("SELECT * FROM users WHERE login='director'")
    if not c.fetchone():
        c.execute("INSERT INTO users (name, role, login, password) VALUES ('Директор', 'director', 'director', '123')")

    # Добавляем учителей, если их нет
    teachers = [
        ("Иванова Мария", "teacher", "9А", "ivanova", "123"),
        ("Петров Сергей", "teacher", "9Б", "petrov", "123"),
        ("Сидорова Анна", "teacher", "10А", "sidorova", "123"),
        ("Козлов Дмитрий", "teacher", "10Б", "kozlov", "123"),
        ("Морозова Елена", "teacher", "11А", "morozova", "123"),
        ("Волков Андрей", "teacher", "11Б", "volkov", "123"),
        ("Зайцева Ольга", "teacher", "7А", "zaitseva", "123"),
    ]

    for name, role, class_name, login, password in teachers:
        c.execute("SELECT * FROM users WHERE login=?", (login,))
        if not c.fetchone():
            c.execute("INSERT INTO users (name, role, class, login, password) VALUES (?, ?, ?, ?, ?)",
                      (name, role, class_name, login, password))

    conn.commit()
    conn.close()


# Инициализируем базу данных при запуске
init_db()


# ========== ФУНКЦИИ РАБОТЫ С БАЗОЙ ==========
def get_next_number():
    """Возвращает следующий номер заявления (APP-001, APP-002...)"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT next FROM counter WHERE id=1")
    next_num = c.fetchone()[0]
    c.execute("UPDATE counter SET next = ? WHERE id=1", (next_num + 1,))
    conn.commit()
    conn.close()
    return f"APP-{next_num:03d}"


# ========== РОУТЫ ==========
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login = request.form['login']
        password = request.form['password']

        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE login=? AND password=?", (login, password))
        user = c.fetchone()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            return redirect(url_for('dashboard'))

        return render_template('login.html', error="Неверный логин или пароль")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    c = conn.cursor()

    # Статистика
    c.execute("SELECT COUNT(*) FROM applications")
    all_apps = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM applications WHERE status='pending'")
    pending = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM applications WHERE status='approved'")
    approved = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM applications WHERE status='rejected'")
    rejected = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM applications WHERE user_id=?", (session['user_id'],))
    my_apps = c.fetchone()[0]

    conn.close()

    return render_template('dashboard.html',
                           user_name=session['user_name'],
                           user_role=session['user_role'],
                           all_apps=all_apps,
                           pending=pending,
                           approved=approved,
                           rejected=rejected,
                           my_apps=my_apps)


@app.route('/apply', methods=['GET', 'POST'])
def apply():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session['user_role'] == 'director':
        return "Директор не может подавать заявления", 403

    if request.method == 'POST':
        app_type = request.form['type']
        date = request.form['date']
        reason = request.form['reason']

        number = get_next_number()

        conn = get_db()
        c = conn.cursor()
        c.execute('''INSERT INTO applications 
                     (number, user_id, user_name, type, date, reason, status, created_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (number, session['user_id'], session['user_name'], app_type, date, reason, 'pending',
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()

        return redirect(url_for('my_apps'))

    return render_template('apply.html')


@app.route('/my_apps')
def my_apps():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM applications WHERE user_id=? ORDER BY created_at DESC", (session['user_id'],))
    applications = c.fetchall()
    conn.close()

    return render_template('my_apps.html', applications=applications)


@app.route('/pending')
def pending():
    if 'user_id' not in session or session['user_role'] != 'director':
        return "Доступ запрещён", 403

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM applications WHERE status='pending' ORDER BY created_at DESC")
    applications = c.fetchall()
    conn.close()

    return render_template('pending.html', applications=applications)


@app.route('/approve/<number>')
def approve(number):
    if 'user_id' not in session or session['user_role'] != 'director':
        return "Доступ запрещён", 403

    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE applications SET status='approved' WHERE number=?", (number,))
    conn.commit()
    conn.close()

    return redirect(url_for('pending'))


@app.route('/reject/<number>', methods=['GET', 'POST'])
def reject(number):
    if 'user_id' not in session or session['user_role'] != 'director':
        return "Доступ запрещён", 403

    if request.method == 'POST':
        reason = request.form['reason']
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE applications SET status='rejected', reject_reason=? WHERE number=?", (reason, number))
        conn.commit()
        conn.close()
        return redirect(url_for('pending'))

    return render_template('reject.html', number=number)


@app.route('/delete/<number>')
def delete_application(number):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    c = conn.cursor()

    # Проверяем права на удаление
    c.execute("SELECT user_id FROM applications WHERE number=?", (number,))
    result = c.fetchone()

    if not result:
        conn.close()
        return "Заявление не найдено", 404

    if result[0] != session['user_id'] and session['user_role'] != 'director':
        conn.close()
        return "У вас нет прав на удаление", 403

    c.execute("DELETE FROM applications WHERE number=?", (number,))
    conn.commit()
    conn.close()

    return redirect(url_for('my_apps'))


# ========== API ДЛЯ КАРТОЧЕК ==========
@app.route('/api/applications')
def api_applications():
    if 'user_id' not in session:
        return {"error": "Не авторизован"}, 401

    status = request.args.get('status', 'all')

    conn = get_db()
    c = conn.cursor()

    if status == 'pending':
        c.execute("SELECT * FROM applications WHERE status='pending' ORDER BY created_at DESC")
    elif status == 'approved':
        c.execute("SELECT * FROM applications WHERE status='approved' ORDER BY created_at DESC")
    elif status == 'rejected':
        c.execute("SELECT * FROM applications WHERE status='rejected' ORDER BY created_at DESC")
    else:
        c.execute("SELECT * FROM applications ORDER BY created_at DESC")

    apps = c.fetchall()
    conn.close()

    # Преобразуем Row в список словарей
    result = []
    for app in apps:
        result.append({
            'number': app['number'],
            'user_name': app['user_name'],
            'type': app['type'],
            'date': app['date'],
            'reason': app['reason'],
            'status': app['status'],
            'reject_reason': app['reject_reason']
        })

    return result


# ========== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ==========
@app.route('/users')
def users():
    if 'user_id' not in session or session['user_role'] != 'director':
        return "Доступ запрещён", 403

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users ORDER BY id")
    users_list = c.fetchall()
    conn.close()

    return render_template('users.html', users=users_list)


@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if 'user_id' not in session or session['user_role'] != 'director':
        return "Доступ запрещён", 403

    if request.method == 'POST':
        name = request.form['name']
        login = request.form['login']
        password = request.form['password']
        role = request.form['role']
        class_name = request.form.get('class', '')

        conn = get_db()
        c = conn.cursor()

        try:
            c.execute("INSERT INTO users (name, role, class, login, password) VALUES (?, ?, ?, ?, ?)",
                      (name, role, class_name, login, password))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Ошибка: пользователь с таким логином уже существует"

        conn.close()
        return redirect(url_for('users'))

    return render_template('add_user.html')


@app.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    if 'user_id' not in session or session['user_role'] != 'director':
        return "Доступ запрещён", 403

    if user_id == session['user_id']:
        return "Нельзя удалить самого себя", 403

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('users'))

@app.route('/api/delete/<number>')
def api_delete_application(number):
    if 'user_id' not in session:
        return {"error": "Не авторизован"}, 401
    
    conn = get_db()
    c = conn.cursor()
    
    # Проверяем, существует ли заявление и есть ли права
    c.execute("SELECT user_id FROM applications WHERE number=?", (number,))
    result = c.fetchone()
    
    if not result:
        conn.close()
        return {"error": "Заявление не найдено"}, 404
    
    # Удалить может: владелец ИЛИ директор
    if result[0] != session['user_id'] and session['user_role'] != 'director':
        conn.close()
        return {"error": "Нет прав"}, 403
    
    c.execute("DELETE FROM applications WHERE number=?", (number,))
    conn.commit()
    conn.close()
    
    return {"success": True}

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
