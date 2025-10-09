from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
import re
from datetime import datetime

app = Flask(__name__)

# ## Upload Folder Configuration ##
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ## SQLAlchemy Configuration ##
# This will be replaced by the Render database URL in production
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_super_secret_key'

db = SQLAlchemy(app)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# === DATABASE MODELS ===

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    issues = db.relationship('Issue', backref='author', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

class Issue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    state = db.Column(db.String(100))
    district = db.Column(db.String(100))
    block = db.Column(db.String(100))
    image_path = db.Column(db.String(100))
    status = db.Column(db.String(20), default='Pending')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<Issue {self.title}>'

class Authority(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    state = db.Column(db.String(100))
    district = db.Column(db.String(100))
    block = db.Column(db.String(100))
    password_hash = db.Column(db.String(256))

    def __repr__(self):
        return f'<Authority {self.username}>'

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

        # Check if user already exists
        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            flash('Username or email already exists.', 'error')
            return redirect(url_for('register'))

        new_user = User(username=username, email=email, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form['username']
        password_candidate = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password_candidate):
            session['logged_in'] = True
            session['username'] = user.username
            session['user_id'] = user.id
            flash('You are now logged in!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Invalid username or password', 'error')
            return redirect(url_for('login'))
    return render_template('login.html', title='Login')


@app.route('/logout')
def logout():
    session.clear()
    flash('You are now logged out.', 'success')
    return redirect(url_for('login'))


@app.route('/profile')
def profile():
    if 'logged_in' in session:
        user_issues = Issue.query.filter_by(user_id=session['user_id']).order_by(Issue.timestamp.desc()).all()
        return render_template('profile.html', username=session['username'], issues=user_issues)
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

        new_issue = Issue(
            title=title,
            description=description,
            category=category,
            location=location,
            state=state,
            district=district,
            block=block,
            user_id=user_id,
            image_path=filename
        )
        db.session.add(new_issue)
        db.session.commit()

        flash('Your issue has been reported successfully!', 'success')
        return redirect(url_for('profile'))


@app.route('/community_feed')
def community_feed():
    try:
        all_issues = Issue.query.order_by(Issue.timestamp.desc()).all()
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
        state = request.form.get('state')
        district = request.form.get('district')
        block = request.form.get('block')
        password = request.form['password']

        if not re.match(r"[^@]+@gov\.in", email):
            flash('Invalid email. Only "@gov.in" emails are allowed.', 'danger')
            return redirect(url_for('register1'))

        hashed_password = generate_password_hash(password)

        if Authority.query.filter_by(username=username).first() or Authority.query.filter_by(email=email).first():
            flash('Username or email already exists for an authority account.', 'danger')
            return redirect(url_for('register1'))

        new_authority = Authority(
            username=username,
            email=email,
            state=state,
            district=district,
            block=block,
            password_hash=hashed_password
        )
        db.session.add(new_authority)
        db.session.commit()

        flash('Authority registration successful! Please log in.', 'success')
        return redirect(url_for('login1'))
    return render_template('register1.html')


@app.route('/login1', methods=['GET', 'POST'])
def login1():
    if request.method == 'POST':
        username = request.form['username']
        password_candidate = request.form['password']
        block = request.form['block']

        authority = Authority.query.filter_by(username=username, block=block).first()

        if authority and check_password_hash(authority.password_hash, password_candidate):
            session['authority_logged_in'] = True
            session['authority_username'] = authority.username
            session['authority_block'] = authority.block
            flash('You are now logged in!', 'success')
            return redirect(url_for('gov_office'))
        else:
            flash('Invalid username, password, or block.', 'danger')
            return redirect(url_for('login1'))
    return render_template('login1.html')


@app.route('/gov_office')
def gov_office():
    if 'authority_logged_in' in session and session.get('authority_block'):
        authority_block = session['authority_block']
        
        all_issues = Issue.query.filter_by(block=authority_block).order_by(Issue.status, Issue.timestamp.desc()).all()
        
        return render_template('Gov_office.html', issues=all_issues, username=session['authority_username'], block=authority_block)
    
    flash('Please log in as an authority to view this page.', 'danger')
    return redirect(url_for('login1'))


@app.route('/update_status/<int:issue_id>', methods=['POST'])
def update_status(issue_id):
    if 'authority_logged_in' not in session:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login1'))

    new_status = request.form['status']
    issue_to_update = Issue.query.get_or_404(issue_id)

    if new_status in ['In Progress', 'Completed']:
        issue_to_update.status = new_status
        db.session.commit()
        flash(f'Issue status updated to "{new_status}"!', 'success')
    
    return redirect(url_for('gov_office'))

# === END OF ROUTES ===
with app.app_context():
        db.create_all()

if __name__ == "__main__":
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        
    # This command will create the tables if they don't exist
    
        
    app.run(debug=True,port=7000)