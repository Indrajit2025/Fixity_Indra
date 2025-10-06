from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL,MySQLdb
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
import re 

app = Flask(__name__)

# ## Upload Folder Configuration ##
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# ## MySQL Configuration ##
app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DB')
# Required for Aiven
app.config['MYSQL_SSL_MODE'] = 'REQUIRED'

mysql = MySQL(app)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# === USER ROUTES ===

@app.route('/')
def fixity():
    return render_template('fixity.html')


@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        try:
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO users(username, email, password_hash) VALUES(%s, %s, %s)", (username, email, hashed_password))
            mysql.connection.commit()
            cur.close()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash('Username or email already exists.', 'error')
            return redirect(url_for('register'))
    return render_template('register.html')


@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form['username']
        password_candidate = request.form['password']
        cur = mysql.connection.cursor()
        result = cur.execute("SELECT * FROM users WHERE username = %s", [username])
        if result > 0:
            data = cur.fetchone()
            user_id = data[0]
            password_hash = data[3]
            if check_password_hash(password_hash, password_candidate):
                session['logged_in'] = True
                session['username'] = username
                session['user_id'] = user_id
                flash('You are now logged in!', 'success')
                return redirect(url_for('profile'))
            else:
                flash('Invalid password', 'error')
                return redirect(url_for('login'))
        else:
            flash('Username not found', 'error')
            return redirect(url_for('login'))
        cur.close()
    return render_template('login.html', title='Login')


@app.route('/logout')
def logout():
    session.clear()
    flash('You are now logged out.', 'success')
    return redirect(url_for('login'))


@app.route('/profile')
def profile():
    if 'logged_in' in session:
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM issues WHERE user_id = %s ORDER BY timestamp DESC", [session['user_id']])
        issues = cur.fetchall()
        cur.close()
        return render_template('profile.html', username=session['username'], issues=issues)
    return redirect(url_for('login'))


@app.route('/report')
def report():
    if 'logged_in' in session:
        return render_template('report.html')
    return redirect(url_for('login'))


@app.route('/submit_report', methods=['POST'])
def submit_report():
    if 'logged_in' not in session:
        flash('Please log in to submit a report.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['issue_title']
        description = request.form['description']
        category = request.form['category']
        location = request.form['zone_area']
        state = request.form['state']
        district = request.form['district']
        block = request.form['block']
        user_id = session['user_id']
        filename = None

        if 'file_upload' in request.files:
            file = request.files['file_upload']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        try:
            cur = mysql.connection.cursor()
            cur.execute(
                """INSERT INTO issues 
                (user_id, title, description, category, location, image_path, status, state, district, block) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (user_id, title, description, category, location, filename, 'Pending', state, district, block)
            )
            mysql.connection.commit()
            cur.close()
            flash('Your issue has been reported successfully!', 'success')
        except Exception as e:
            flash(f'An error occurred: {e}', 'danger')

        return redirect(url_for('profile'))
    

@app.route('/community_feed')
def community_feed():
    try:
        # Using a dictionary cursor to fetch data by column name
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # This query fetches all necessary details for the community feed
        cur.execute("""
            SELECT 
                i.id, i.title, i.description, i.location, i.image_path, 
                i.status, i.district, i.block,
                u.username
            FROM issues i
            JOIN users u ON i.user_id = u.id 
            ORDER BY i.timestamp DESC
        """)
        all_issues = cur.fetchall()
        cur.close()
        return render_template('all_reported.html', issues=all_issues)
    except Exception as e:
        flash(f"An error occurred while fetching the community feed: {e}", "danger")
        return redirect(url_for('fixity'))

# === AUTHORITY ROUTES ===

@app.route('/register1', methods=['GET', 'POST'])
def register1():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        state = request.form.get('state') # .get() makes it optional
        district = request.form.get('district')
        block = request.form.get('block')
        password = request.form['password']

        if not re.match(r"[^@]+@gov\.in", email):
            flash('Invalid email. Only "@gov.in" emails are allowed.', 'danger')
            return redirect(url_for('register1'))

        hashed_password = generate_password_hash(password)

        try:
            cur = mysql.connection.cursor()
            # Updated INSERT statement without pincodes
            cur.execute(
                "INSERT INTO authorities(username, email, state, district, block, password_hash) VALUES(%s, %s, %s, %s, %s, %s)",
                (username, email, state, district, block, hashed_password)
            )
            mysql.connection.commit()
            cur.close()
            flash('Authority registration successful! Please log in.', 'success')
            return redirect(url_for('login1'))
        except Exception as e:
            flash('Username or email already exists for an authority account.', 'danger')
            return redirect(url_for('register1'))
            
    return render_template('register1.html')


@app.route('/login1', methods=['GET', 'POST'])
def login1():
    if request.method == 'POST':
        username = request.form['username']
        password_candidate = request.form['password']
        block = request.form['block']

        cur = mysql.connection.cursor()
        # Using a dictionary cursor to fetch by column name
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor) 
        
        result = cur.execute("SELECT * FROM authorities WHERE username = %s AND block = %s", (username, block))

        if result > 0:
            data = cur.fetchone()
            # Fetching by name is safer than by index
            password_hash = data.get('password_hash') 

            # CRITICAL FIX: Check if password_hash exists before using it
            if password_hash and check_password_hash(password_hash, password_candidate):
                session['authority_logged_in'] = True
                session['authority_username'] = data['username']
                session['authority_block'] = data['block']
                
                flash('You are now logged in!', 'success')
                return redirect(url_for('gov_office'))
            else:
                flash('Invalid username or password', 'danger')
                return redirect(url_for('login1'))
        else:
            flash('Authority not found for the specified block.', 'danger')
            return redirect(url_for('login1'))
        cur.close()

    return render_template('login1.html')


@app.route('/gov_office')
def gov_office():
    if 'authority_logged_in' in session and session.get('authority_block'):
        authority_block = session['authority_block']
        
        cur = mysql.connection.cursor()
        
        # Filter issues based on the logged-in authority's block
        query = """
            SELECT issues.*, users.username
            FROM issues 
            JOIN users ON issues.user_id = users.id 
            WHERE issues.block = %s
            ORDER BY FIELD(status, 'Pending', 'In Progress', 'Completed'), issues.timestamp DESC
        """
        cur.execute(query, [authority_block])
        
        all_issues = cur.fetchall()
        cur.close()
        return render_template('Gov_office.html', issues=all_issues, username=session['authority_username'], block=authority_block)
    
    flash('Please log in as an authority to view this page.', 'danger')
    return redirect(url_for('login1'))


@app.route('/update_status/<int:issue_id>', methods=['POST'])
def update_status(issue_id):
    if 'authority_logged_in' not in session:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login1'))

    new_status = request.form['status']
    if new_status in ['In Progress', 'Completed']:
        try:
            cur = mysql.connection.cursor()
            cur.execute("UPDATE issues SET status = %s WHERE id = %s", (new_status, issue_id))
            mysql.connection.commit()
            cur.close()
            flash(f'Issue status updated to "{new_status}"!', 'success')
        except Exception as e:
            flash(f'Database error: {e}', 'danger')
    
    return redirect(url_for('gov_office'))

# === END OF ROUTES ===

if __name__ == "__main__":
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True,port=7000)