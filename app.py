from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import mysql.connector
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Database connection
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="catnest"
    )

# ---------------- HOME -----------------
@app.route('/')
def home():
    return redirect(url_for('login'))

# ---------------- LOGIN -----------------
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

# ---------------- SIGNUP -----------------
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
        cursor.execute(
            "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
            (username, email, password, role)
        )
        conn.commit()
        conn.close()
        flash('Signup successful! Please login.')
        return redirect(url_for('login'))
    return render_template('signup.html', role=role)

# ---------------- SELLER DASHBOARD -----------------
@app.route('/seller', methods=['GET', 'POST'])
def seller_dashboard():
    if 'role' not in session or session['role'] != 'seller':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        file = request.files.get('photo')
        filename = None
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        age = request.form['age']
        gender = request.form['gender']
        price = request.form['price']
        breed = request.form['breed']

        cursor.execute(
            "INSERT INTO cats (photo, age, gender, price, breed, seller_id) VALUES (%s, %s, %s, %s, %s, %s)",
            (filename, age, gender, price, breed, session['user_id'])
        )
        conn.commit()

    # Fetch seller's cats with love count
    cursor.execute("""
        SELECT cats.*, 
               (SELECT COUNT(*) FROM loves WHERE loves.cat_id = cats.id) AS love_count
        FROM cats
        WHERE seller_id = %s
    """, (session['user_id'],))
    cats = cursor.fetchall()

    # Fetch comments for seller's cats
    cursor.execute("""
        SELECT comments.*, users.username 
        FROM comments
        JOIN users ON comments.buyer_id = users.id
        WHERE comments.cat_id IN (SELECT id FROM cats WHERE seller_id = %s)
    """, (session['user_id'],))
    comments = cursor.fetchall()
    conn.close()

    # Organize comments by cat_id
    comments_by_cat = {cat['id']: [] for cat in cats}
    for c in comments:
        comments_by_cat.setdefault(c['cat_id'], []).append(c)

    return render_template('seller_dashboard.html', cats=cats, comments_by_cat=comments_by_cat)

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

@app.route('/edit_cat/<int:cat_id>', methods=['GET', 'POST'])
def edit_cat(cat_id):
    if 'role' not in session or session['role'] != 'seller':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM cats WHERE id=%s AND seller_id=%s", (cat_id, session['user_id']))
    cat = cursor.fetchone()

    if not cat:
        conn.close()
        flash("Cat not found or you don’t have permission to edit it.")
        return redirect(url_for('seller_dashboard'))

    if request.method == 'POST':
        age = request.form['age']
        gender = request.form['gender']
        price = request.form['price']
        breed = request.form['breed']

        file = request.files.get('photo')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            filename = cat['photo']

        cursor.execute("""
            UPDATE cats SET photo=%s, age=%s, gender=%s, price=%s, breed=%s
            WHERE id=%s AND seller_id=%s
        """, (filename, age, gender, price, breed, cat_id, session['user_id']))

        conn.commit()
        conn.close()
        flash("Cat post updated successfully!")
        return redirect(url_for('seller_dashboard'))

    conn.close()
    return render_template('edit_cat.html', cat=cat)

# ---------------- BUYER DASHBOARD -----------------
@app.route('/buyer')
def buyer_dashboard():
    if 'role' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))

    sort = request.args.get('sort')
    breed = request.args.get('breed')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch cats with love count and buyer's rating
    query = """
        SELECT cats.*, users.username AS seller_name,
               (SELECT COUNT(*) FROM loves WHERE loves.cat_id = cats.id) AS love_count,
               (SELECT rating FROM cat_ratings WHERE cat_ratings.cat_id = cats.id AND cat_ratings.buyer_id = %s) AS my_rating
        FROM cats
        JOIN users ON cats.seller_id = users.id
    """
    params = [session['user_id']]

    if breed:
        query += " WHERE cats.breed LIKE %s"
        params.append('%' + breed + '%')

    if sort == 'price':
        query += " ORDER BY price ASC"

    cursor.execute(query, params)
    cats = cursor.fetchall()

    # Fetch all comments
    cursor.execute("""
        SELECT comments.*, users.username
        FROM comments
        JOIN users ON comments.buyer_id = users.id
    """)
    comments = cursor.fetchall()
    conn.close()

    # Organize comments by cat_id
    comments_by_cat = {cat['id']: [] for cat in cats}
    for c in comments:
        comments_by_cat.setdefault(c['cat_id'], []).append(c)

    return render_template('buyer_dashboard.html', cats=cats, comments_by_cat=comments_by_cat)

# ---------------- COMMENTS -----------------
@app.route('/comment/<int:cat_id>', methods=['POST'])
def comment(cat_id):
    if 'role' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))

    comment_text = request.form['comment']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO comments (cat_id, buyer_id, comment) VALUES (%s, %s, %s)",
        (cat_id, session['user_id'], comment_text)
    )
    conn.commit()
    conn.close()
    flash('Comment added!')
    return redirect(url_for('buyer_dashboard'))

# ---------------- CAT RATING -----------------
@app.route('/rate_cat/<int:cat_id>', methods=['POST'])
def rate_cat(cat_id):
    if 'role' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))

    rating_value = int(request.form['rating'])
    buyer_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cat_ratings (cat_id, buyer_id, rating)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE rating = VALUES(rating)
    """, (cat_id, buyer_id, rating_value))
    conn.commit()
    conn.close()
    return redirect(url_for('buyer_dashboard'))

# ---------------- LOVE REACT -----------------
@app.route('/love/<int:cat_id>', methods=['POST'])
def love_cat(cat_id):
    if 'role' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))

    buyer_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO loves (buyer_id, cat_id) VALUES (%s, %s)",
            (buyer_id, cat_id)
        )
        conn.commit()
    except mysql.connector.errors.IntegrityError:
        pass

    conn.close()
    return redirect(url_for('buyer_dashboard'))

# ---------------- WISHLIST FEATURE -----------------
@app.route('/add_to_wishlist/<int:cat_id>', methods=['POST'])
def add_to_wishlist(cat_id):
    if 'role' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))

    buyer_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO wishlist (buyer_id, cat_id) VALUES (%s, %s)",
            (buyer_id, cat_id)
        )
        conn.commit()
        flash('Cat added to your wishlist!')
    except mysql.connector.errors.IntegrityError:
        flash('This cat is already in your wishlist.')
    conn.close()
    return redirect(url_for('buyer_dashboard'))

@app.route('/wishlist')
def wishlist():
    if 'role' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))

    buyer_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT cats.*, users.username AS seller_name
        FROM wishlist
        JOIN cats ON wishlist.cat_id = cats.id
        JOIN users ON cats.seller_id = users.id
        WHERE wishlist.buyer_id = %s
    """, (buyer_id,))
    wishlist_cats = cursor.fetchall()
    conn.close()

    return render_template('wishlist.html', cats=wishlist_cats)

# ---------------- LOGOUT -----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
