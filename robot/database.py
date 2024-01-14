import sqlite3
import os

def initialize():
    if not os.path.exists('database'):
        os.makedirs('database')

    conn = sqlite3.connect(os.path.join('database', 'tokens.db'))
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS tokens (
        token TEXT PRIMARY KEY,
        username TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER,
        bot_token TEXT,
        FOREIGN KEY (bot_token) REFERENCES tokens(token)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
        name TEXT PRIMARY KEY,
        text  TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS payment_details (
        type TEXT PRIMARY KEY,
        text TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS daily_mailings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time TEXT,
        text TEXT,
        photo_path TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS cities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        city_id INTEGER,
        FOREIGN KEY (city_id) REFERENCES cities(id)
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS product_details (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        klad_type TEXT,
        price REAL,
        districts TEXT,
        FOREIGN KEY (product_id) REFERENCES products(id)
    )''')

    cursor.execute("INSERT OR IGNORE INTO payment_details (type, text) VALUES ('card', 'Пока не установлено.')")
    cursor.execute("INSERT OR IGNORE INTO payment_details (type, text) VALUES ('btc', 'Пока не установлено.')")
    cursor.execute("INSERT OR IGNORE INTO payment_details (type, text) VALUES ('ltc', 'Пока не установлено.')")

    cursor.execute("INSERT OR IGNORE INTO settings (name, text) VALUES ('help', 'https://t.me/durov')")
    cursor.execute("INSERT OR IGNORE INTO settings (name, text) VALUES ('operator_link', 'https://t.me/durov')")
    cursor.execute("INSERT OR IGNORE INTO settings (name, text) VALUES ('work_link', 'https://t.me/durov')")

    conn.commit()
    conn.close()

def add_city_if_not_exists(city_name):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM cities WHERE name = ?", (city_name,))
        result = cursor.fetchone()
        if result:
            return result[0]
        cursor.execute("INSERT INTO cities (name) VALUES (?)", (city_name,))
        conn.commit()
        return cursor.lastrowid

def get_products_by_city(city_id):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM products WHERE city_id = ?", (city_id,))
        return cursor.fetchall()

def add_product(product_name, city_id):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO products (name, city_id) VALUES (?, ?)", (product_name, city_id))
        conn.commit()
        return cursor.lastrowid

def get_total_users_count():
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        return cursor.fetchone()[0]

def get_users_count_of_bot(bot_token):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE bot_token = ?", (bot_token,))
        return cursor.fetchone()[0]

def delete_city(city_id):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM cities WHERE id = ?", (city_id,))
        conn.commit()

def delete_product(product_id):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM product_details WHERE product_id = ?", (product_id,))
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()

def get_full_database_info():
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()

        
        cursor.execute("SELECT * FROM cities")
        cities_info = cursor.fetchall()
        cities_output = ["Города:"] + [f"ID: {city[0]}, Название: {city[1]}" for city in cities_info]
        
        cursor.execute("SELECT * FROM products")
        products_info = cursor.fetchall()
        products_output = ["Товары:"] + [f"ID: {prod[0]}, Название: {prod[1]}, Категория ID: {prod[2]}" for prod in products_info]

        return "\n".join(cities_output + products_output)

def add_product_details(product_id, klad_type, price, districts):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO product_details (product_id, klad_type, price, districts) VALUES (?, ?, ?, ?)", (product_id, klad_type, price, districts))
        conn.commit()

def get_product_details(product_id):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT klad_type, price, districts FROM product_details WHERE product_id = ?", (product_id,))
        return cursor.fetchall()

def get_cities():
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cities")
        return cursor.fetchall()

def get_product_price(product_id):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT price FROM product_details WHERE product_id = ?", (product_id,))
        result = cursor.fetchone()
        return result[0] if result else None

def get_operator_link():
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT text FROM settings WHERE name = 'operator_link'")
        return cursor.fetchone()[0]

def set_operator_link(new_text):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE settings SET text = ? WHERE name = 'operator_link'", (new_text,))
        conn.commit()

def get_city_name(city_id):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM cities WHERE id = ?", (city_id,))
        result = cursor.fetchone()
        return result[0] if result else None

def get_work_link():
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT text FROM settings WHERE name = 'work_link'")
        return cursor.fetchone()[0]

def set_work_link(new_text):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE settings SET text = ? WHERE name = 'work_link'", (new_text,))
        conn.commit()

def get_product_name(product_id):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM products WHERE id = ?", (product_id,))
        result = cursor.fetchone()
        return result[0] if result else None

def add_daily_mailing(time, text, photo_path):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO daily_mailings (time, text, photo_path) VALUES (?, ?, ?)",
                       (time, text, photo_path))
        conn.commit()

def delete_daily_mailing(id):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM daily_mailings WHERE id = ?", (id,))
        conn.commit()

def get_daily_mailings():
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM daily_mailings")
        return cursor.fetchall()

def get_daily_mailing_by_id(id):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM daily_mailings WHERE id = ?", (id,))
        return cursor.fetchone()

def add_token(token, username):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tokens (token, username) VALUES (?, ?)", (token, username))
        conn.commit()

def delete_token(token):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tokens WHERE token = ?", (token,))
        conn.commit()

def get_tokens():
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT token, username FROM tokens")
        return cursor.fetchall()

def get_bot_data(token):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username, token FROM tokens WHERE token = ?", (token,))
        return cursor.fetchone()

def add_user(user_id, bot_token):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (user_id, bot_token) VALUES (?, ?)", (user_id, bot_token))
        conn.commit()

def get_users_by_token(bot_token):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE bot_token = ?", (bot_token,))
        return cursor.fetchall()

def check_user_exists(user_id, bot_token):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE user_id = ? AND bot_token = ?", (user_id, bot_token))
        return cursor.fetchone() is not None

def get_help_text():
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT text FROM settings WHERE name = 'help'")
        return cursor.fetchone()[0]

def set_help_text(new_text):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE settings SET text = ? WHERE name = 'help'", (new_text,))
        conn.commit()

def get_preorder_text():
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT text FROM settings WHERE name = 'preorder'")
        return cursor.fetchone()[0]

def set_preorder_text(new_text):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE settings SET text = ? WHERE name = 'preorder'", (new_text,))
        conn.commit()

def get_payment_details(payment_type):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT text FROM payment_details WHERE type = ?", (payment_type,))
        row = cursor.fetchone()
        return row[0] if row else "Реквизиты не найдены."

def set_payment_details(payment_type, new_text):
    with sqlite3.connect(os.path.join('database', 'tokens.db')) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE payment_details SET text = ? WHERE type = ?", (new_text, payment_type))
        conn.commit()
