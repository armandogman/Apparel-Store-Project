from flask import Flask, render_template, request, redirect, url_for, session, abort
import mysql.connector
import bcrypt
import re
from datetime import timedelta

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=1)
)

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '$Fishingrod2431',
    'database': 'myDB'
}

# Database Utilities
def create_connection(with_db=True):
    if with_db:
        connection = mysql.connector.connect(**db_config)
    else:
        tmp = {'host': db_config['host'], 'user': db_config['user'], 'password': db_config['password']}
        connection = mysql.connector.connect(**tmp)
    return connection

def hash_password(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def check_password(password, hashed_password):
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def validate_password(password):
    pattern = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$"
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not re.match(pattern, password):
        raise ValueError(
            "Password must include at least one uppercase letter, one lowercase letter, one number, and one special character."
        )

def initialize_database():
    conn = create_connection()
    cursor = conn.cursor()
    # Create tables if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100) NOT NULL,
            pass VARCHAR(255) NOT NULL,
            UNIQUE(name),
            UNIQUE(email)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user VARCHAR(50) NOT NULL,
            msg VARCHAR(500) NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cart (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            item_name VARCHAR(255) NOT NULL,
            quantity INT DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

# Routes
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        try:
            # Validate password strength
            validate_password(password)
            
            # Check for duplicate username/email
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE name=%s OR email=%s", (username, email))
            if cursor.fetchone():
                return render_template('register.html', error="Username or email already exists.")
            
            # Hash password and save user
            hashed_password = hash_password(password)
            cursor.execute("INSERT INTO users (name, email, pass) VALUES (%s, %s, %s)", (username, email, hashed_password))
            conn.commit()
            cursor.close()
            conn.close()
            return redirect(url_for('login'))
        except ValueError as ve:
            return render_template('register.html', error=str(ve))
        except Exception as e:
            print(e)
            return render_template('register.html', error="An unexpected error occurred.")
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, email, pass FROM users WHERE name=%s", (username,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            if not user or not check_password(password, user[3]):
                abort(403, "Invalid credentials.")
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['email'] = user[2]
            return redirect(url_for('profile'))
        except Exception as e:
            print(f"Error during login: {e}")
            abort(500, "An error occurred during login.")
    return render_template('login.html')

@app.route('/profile')
def profile():
    if 'username' in session:
        return render_template('profile.html', username=session['username'], email=session['email'])
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/view_users')
def view_users():
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email FROM users")
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('view_users.html', users=users)
    except Exception as e:
        print(e)
        abort(500, "Unable to fetch users.")

@app.route('/board', methods=['GET', 'POST'])
def message_board():
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        message = request.form['message']
        try:
            conn = create_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (user, msg) VALUES (%s, %s)", (session['username'], message))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(e)
            abort(500, "Unable to post message.")
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user, msg FROM messages")
        messages = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('board.html', messages=messages)
    except Exception as e:
        print(e)
        abort(500, "Unable to fetch messages.")

@app.route('/cart', methods=['GET', 'POST'])
def view_cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        conn = create_connection()
        cursor = conn.cursor()
        if request.method == 'POST':
            item_name = request.form['item_name']
            quantity = request.form.get('quantity', 1)
            cursor.execute("""
                INSERT INTO cart (user_id, item_name, quantity)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
            """, (session['user_id'], item_name, quantity))
            conn.commit()
        cursor.execute("SELECT item_name, quantity FROM cart WHERE user_id=%s", (session['user_id'],))
        cart_items = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('cart.html', cart_items=cart_items)
    except Exception as e:
        print(e)
        abort(500, "Unable to fetch or update cart.")

# Error Handlers
@app.errorhandler(400)
def bad_request(error):
    return render_template('400.html', message=error.description), 400

@app.errorhandler(403)
def forbidden(error):
    return render_template('403.html', message=error.description), 403

@app.errorhandler(409)
def conflict(error):
    return render_template('409.html', message=error.description), 409

@app.errorhandler(500)
def internal_server_error(error):
    return render_template('500.html', message=error.description), 500

if __name__ == '__main__':
    initialize_database()
    app.run(debug=True)
