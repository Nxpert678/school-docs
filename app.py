from flask import Flask, render_template, request, redirect, url_for, session
import json
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'school_secret_key_2026'

# ========== РАБОТА С ПОЛЬЗОВАТЕЛЯМИ ==========
def load_users():
    if os.path.exists('users.json'):
        with open('users.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    # Создаём тестовых пользователей
    users = {
        "1": {"id": 1, "name": "Директор", "role": "director", "login": "director", "password": "123"},
        "2": {"id": 2, "name": "Иванова Мария", "role": "teacher", "class": "9А", "login": "teacher", "password": "123"}
    }
    with open('users.json', 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    return users

def save_users(users):
    with open('users.json', 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

# ========== РАБОТА С ЗАЯВЛЕНИЯМИ ==========
def load_applications():
    if os.path.exists('applications.json'):
        with open('applications.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_applications(apps):
    with open('applications.json', 'w', encoding='utf-8') as f:
        json.dump(apps, f, ensure_ascii=False, indent=2)

def get_next_number():
    counter_file = 'counter.json'
    if os.path.exists(counter_file):
        with open(counter_file, 'r', encoding='utf-8') as f:
            counter = json.load(f)
    else:
        counter = {"next": 1}
    
    num = counter["next"]
    counter["next"] += 1
    
    with open(counter_file, 'w', encoding='utf-8') as f:
        json.dump(counter, f)
    
    return f"APP-{num:03d}"

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
        
        users = load_users()
        for user_id, user in users.items():
            if user['login'] == login and user['password'] == password:
                session['user_id'] = user_id
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
    
    apps = load_applications()
    user_id = session['user_id']
    
    all_apps = len(apps)
    pending = sum(1 for a in apps.values() if a['status'] == 'pending')
    approved = sum(1 for a in apps.values() if a['status'] == 'approved')
    rejected = sum(1 for a in apps.values() if a['status'] == 'rejected')
    my_apps = sum(1 for a in apps.values() if a['user_id'] == user_id)
    
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
        
        apps = load_applications()
        number = get_next_number()
        
        apps[number] = {
            "number": number,
            "user_id": session['user_id'],
            "user_name": session['user_name'],
            "type": app_type,
            "date": date,
            "reason": reason,
            "status": "pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_applications(apps)
        
        return redirect(url_for('my_apps'))
    
    return render_template('apply.html')

@app.route('/my_apps')
def my_apps():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    apps = load_applications()
    user_id = session['user_id']
    my_apps_list = [a for a in apps.values() if a['user_id'] == user_id]
    my_apps_list.reverse()
    
    return render_template('my_apps.html', applications=my_apps_list)

@app.route('/pending')
def pending():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if session['user_role'] != 'director':
        return "Доступ только для директора", 403
    
    apps = load_applications()
    pending_list = [a for a in apps.values() if a['status'] == 'pending']
    
    return render_template('pending.html', applications=pending_list)

@app.route('/approve/<number>')
def approve(number):
    if 'user_id' not in session or session['user_role'] != 'director':
        return "Доступ запрещён", 403
    
    apps = load_applications()
    if number in apps and apps[number]['status'] == 'pending':
        apps[number]['status'] = 'approved'
        save_applications(apps)
    
    return redirect(url_for('pending'))

@app.route('/reject/<number>', methods=['GET', 'POST'])
def reject(number):
    if 'user_id' not in session or session['user_role'] != 'director':
        return "Доступ запрещён", 403
    
    if request.method == 'POST':
        reason = request.form['reason']
        apps = load_applications()
        if number in apps and apps[number]['status'] == 'pending':
            apps[number]['status'] = 'rejected'
            apps[number]['reject_reason'] = reason
            save_applications(apps)
        return redirect(url_for('pending'))
    
    return render_template('reject.html', number=number)

@app.route('/delete/<number>')
def delete_application(number):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    apps = load_applications()
    
    if number not in apps:
        return "Заявление не найдено", 404
    
    # Проверка прав: удалять может только владелец или директор
    if apps[number]['user_id'] != session['user_id'] and session['user_role'] != 'director':
        return "У вас нет прав на удаление этого заявления", 403
    
    # Полностью удаляем заявление из словаря
    del apps[number]
    save_applications(apps)
    
    # Возвращаемся на страницу моих заявлений
    return redirect(url_for('my_apps'))

# ========== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (ДЛЯ ДИРЕКТОРА) ==========
@app.route('/users')
def users():
    if 'user_id' not in session or session['user_role'] != 'director':
        return "Доступ запрещён", 403
    
    users_data = load_users()
    users_list = list(users_data.values())
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
        
        users = load_users()
        
        # Проверка: логин не должен повторяться
        for user in users.values():
            if user['login'] == login:
                return "Ошибка: пользователь с таким логином уже существует"
        
        new_id = max(int(id) for id in users.keys()) + 1
        
        users[str(new_id)] = {
            "id": new_id,
            "name": name,
            "role": role,
            "login": login,
            "password": password,
            "class": class_name
        }
        save_users(users)
        return redirect(url_for('users'))
    
    return render_template('add_user.html')

@app.route('/delete_user/<user_id>')
def delete_user(user_id):
    if 'user_id' not in session or session['user_role'] != 'director':
        return "Доступ запрещён", 403
    
    users = load_users()
    if user_id in users and user_id != session['user_id']:
        del users[user_id]
        save_users(users)
    
    return redirect(url_for('users'))
# ========== API ДЛЯ ПОЛУЧЕНИЯ ЗАЯВЛЕНИЙ (ДЛЯ МОДАЛЬНЫХ ОКОН) ==========

@app.route('/api/applications')
def api_applications():
    if 'user_id' not in session:
        return {"error": "Не авторизован"}, 401
    
    status = request.args.get('status', 'all')
    apps = load_applications()
    apps_list = list(apps.values())
    
    # Фильтрация по статусу
    if status == 'pending':
        apps_list = [a for a in apps_list if a['status'] == 'pending']
    elif status == 'approved':
        apps_list = [a for a in apps_list if a['status'] == 'approved']
    elif status == 'rejected':
        apps_list = [a for a in apps_list if a['status'] == 'rejected']
    
    # Сортировка: новые сверху
    apps_list.reverse()
    
    return apps_list
# ========== ЗАПУСК ==========
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
