from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import mysql.connector

app = Flask(__name__)
app.secret_key = 'your_secret_key'

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Database connection function
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="catnest"
    )

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            if user['role'] == 'seller':
                return redirect(url_for('seller_dashboard'))
            else:
                return redirect(url_for('buyer_dashboard'))
        else:
            flash('Invalid credentials!')
    return render_template('login.html')

@app.route('/signup_role')
def signup_role():
    return render_template('signup_role.html')

@app.route('/signup/<role>', methods=['GET', 'POST'])
def signup(role):
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)", 
                       (username, email, password, role))
        conn.commit()
        conn.close()
        flash('Signup successful! Please login.')
        return redirect(url_for('login'))
    return render_template('signup.html', role=role)

@app.route('/seller', methods=['GET', 'POST'])
def seller_dashboard():
    if 'role' not in session or session['role'] != 'seller':
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        file = request.files['photo']
        filename = file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        age = request.form['age']
        gender = request.form['gender']
        price = request.form['price']
        cursor.execute("INSERT INTO cats (photo, age, gender, price, seller_id) VALUES (%s, %s, %s, %s, %s)",
                       (filename, age, gender, price, session['user_id']))
        conn.commit()
    cursor.execute("SELECT * FROM cats WHERE seller_id=%s", (session['user_id'],))
    cats = cursor.fetchall()
    conn.close()
    return render_template('seller_dashboard.html', cats=cats)

@app.route('/delete_cat/<int:cat_id>')
def delete_cat(cat_id):
    if 'role' not in session or session['role'] != 'seller':
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cats WHERE id=%s AND seller_id=%s", (cat_id, session['user_id']))
    conn.commit()
    conn.close()
    flash('Cat deleted successfully.')
    return redirect(url_for('seller_dashboard'))

@app.route('/buyer')
def buyer_dashboard():
    if 'role' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))
    sort = request.args.get('sort')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = "SELECT cats.*, users.username as seller_name FROM cats JOIN users ON cats.seller_id = users.id"
    if sort == 'price':
        query += " ORDER BY price ASC"
    cursor.execute(query)
    cats = cursor.fetchall()
    conn.close()
    return render_template('buyer_dashboard.html', cats=cats)

@app.route('/comment/<int:cat_id>', methods=['POST'])
def comment(cat_id):
    if 'role' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))
    comment_text = request.form['comment']
    rating = int(request.form['rating'])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO comments (cat_id, buyer_id, comment, rating) VALUES (%s, %s, %s, %s)",
                   (cat_id, session['user_id'], comment_text, rating))
    conn.commit()
    conn.close()
    flash('Comment and rating added!')
    return redirect(url_for('buyer_dashboard'))



#__________________________________________________________________________
@app.route('/rate/<int:seller_id>', methods=['POST'])
def rate(seller_id):
    if 'user_id' not in session or session['role'] != 'buyer':
        return redirect('/login')

    buyer_id = session['user_id']
    rating_value = int(request.form['rating'])

    cur = mysql.connection.cursor()
    # Either update if already rated, or insert new
    cur.execute("SELECT id FROM ratings WHERE buyer_id=%s AND seller_id=%s", (buyer_id, seller_id))
    existing = cur.fetchone()

    if existing:
        cur.execute("UPDATE ratings SET rating=%s WHERE id=%s", (rating_value, existing[0]))
    else:
        cur.execute("INSERT INTO ratings (buyer_id, seller_id, rating) VALUES (%s, %s, %s)",
                    (buyer_id, seller_id, rating_value))

    mysql.connection.commit()
    cur.close()

    return redirect('/buyer')








#______________________________________________________________________________
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
