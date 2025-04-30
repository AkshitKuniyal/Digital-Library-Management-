from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import random

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
db = SQLAlchemy(app)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin' or 'student'
    full_name = db.Column(db.String(100))
    student_id = db.Column(db.String(50), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    isbn = db.Column(db.String(20), unique=True, nullable=False)
    publisher = db.Column(db.String(100))
    category = db.Column(db.String(50))
    description = db.Column(db.Text)
    quantity = db.Column(db.Integer, default=1)
    available = db.Column(db.Integer, default=1)
    cover_image = db.Column(db.String(100))
    added_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Book {self.title}>'

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    return_date = db.Column(db.DateTime)
    due_date = db.Column(db.DateTime, default=datetime.utcnow() + timedelta(days=14))
    status = db.Column(db.String(20), default='borrowed')  # 'borrowed', 'returned', 'overdue'
    fine_amount = db.Column(db.Float, default=0.0)
    
    book = db.relationship('Book', backref='transactions')
    user = db.relationship('User', backref='transactions')
    
    def __repr__(self):
        return f'<Transaction {self.id}>'

# Create tables
with app.app_context():
    db.create_all()

# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

def calculate_fine(due_date):
    if datetime.utcnow() > due_date:
        days_overdue = (datetime.utcnow() - due_date).days
        return days_overdue * 0.50  # $0.50 per day fine
    return 0.0

# Middleware to check login status
@app.before_request
def before_request():
    allowed_routes = ['login', 'static']
    if request.endpoint not in allowed_routes and 'user_id' not in session:
        return redirect(url_for('login'))

# Routes
@app.route('/')
def login():
    if 'user_id' in session:
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_post():
    username = request.form.get('username')
    password = request.form.get('password')
    
    user = User.query.filter_by(username=username).first()
    
    if not user or not check_password_hash(user.password, password):
        flash('Invalid username or password', 'danger')
        return redirect(url_for('login'))
    
    session['user_id'] = user.id
    session['username'] = user.username
    session['role'] = user.role
    
    if user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    else:
        return redirect(url_for('student_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Admin Routes
@app.route('/admin/dashboard')
def admin_dashboard():
    # Statistics for dashboard
    total_books = Book.query.count()
    total_users = User.query.filter_by(role='student').count()
    total_borrowed = Transaction.query.filter_by(status='borrowed').count()
    overdue_books = Transaction.query.filter(Transaction.due_date < datetime.utcnow(), 
                                           Transaction.status == 'borrowed').count()
    
    # Recent transactions
    recent_transactions = Transaction.query.order_by(Transaction.issue_date.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                         total_books=total_books,
                         total_users=total_users,
                         total_borrowed=total_borrowed,
                         overdue_books=overdue_books,
                         recent_transactions=recent_transactions)

@app.route('/admin/books')
def admin_books():
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    
    if search:
        books = Book.query.filter(
            (Book.title.contains(search)) | 
            (Book.author.contains(search)) |
            (Book.isbn.contains(search))
        ).paginate(page=page, per_page=10)
    else:
        books = Book.query.order_by(Book.title).paginate(page=page, per_page=10)
    
    return render_template('admin/books.html', books=books, search=search)

@app.route('/admin/books/add', methods=['GET', 'POST'])
def add_book():
    if request.method == 'POST':
        title = request.form.get('title')
        author = request.form.get('author')
        isbn = request.form.get('isbn')
        publisher = request.form.get('publisher')
        category = request.form.get('category')
        description = request.form.get('description')
        quantity = int(request.form.get('quantity', 1))
        
        # Check if ISBN already exists
        if Book.query.filter_by(isbn=isbn).first():
            flash('A book with this ISBN already exists', 'danger')
            return redirect(url_for('add_book'))
        
        # Handle file upload
        cover_image = None
        if 'cover_image' in request.files:
            file = request.files['cover_image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                cover_image = filename
        
        new_book = Book(
            title=title,
            author=author,
            isbn=isbn,
            publisher=publisher,
            category=category,
            description=description,
            quantity=quantity,
            available=quantity,
            cover_image=cover_image,
            added_by=session['user_id']
        )
        
        db.session.add(new_book)
        db.session.commit()
        
        flash('Book added successfully', 'success')
        return redirect(url_for('admin_books'))
    
    return render_template('admin/add_book.html')

@app.route('/admin/books/edit/<int:id>', methods=['GET', 'POST'])
def edit_book(id):
    book = Book.query.get_or_404(id)
    
    if request.method == 'POST':
        book.title = request.form.get('title')
        book.author = request.form.get('author')
        book.publisher = request.form.get('publisher')
        book.category = request.form.get('category')
        book.description = request.form.get('description')
        
        # Handle quantity changes
        new_quantity = int(request.form.get('quantity', 1))
        if new_quantity > book.quantity:
            book.available += (new_quantity - book.quantity)
        elif new_quantity < book.quantity:
            book.available = max(0, book.available - (book.quantity - new_quantity))
        book.quantity = new_quantity
        
        # Handle file upload
        if 'cover_image' in request.files:
            file = request.files['cover_image']
            if file and allowed_file(file.filename):
                # Delete old image if exists
                if book.cover_image and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], book.cover_image)):
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], book.cover_image))
                
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                book.cover_image = filename
        
        db.session.commit()
        flash('Book updated successfully', 'success')
        return redirect(url_for('admin_books'))
    
    return render_template('admin/edit_book.html', book=book)

@app.route('/admin/books/delete/<int:id>')
def delete_book(id):
    book = Book.query.get_or_404(id)
    
    # Check if book is borrowed
    borrowed_count = Transaction.query.filter_by(book_id=id, status='borrowed').count()
    if borrowed_count > 0:
        flash('Cannot delete book that is currently borrowed', 'danger')
        return redirect(url_for('admin_books'))
    
    # Delete cover image if exists
    if book.cover_image and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], book.cover_image)):
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], book.cover_image))
    
    # Delete transactions related to this book
    Transaction.query.filter_by(book_id=id).delete()
    
    db.session.delete(book)
    db.session.commit()
    
    flash('Book deleted successfully', 'success')
    return redirect(url_for('admin_books'))

@app.route('/admin/users')
def admin_users():
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    
    if search:
        users = User.query.filter(
            (User.username.contains(search)) | 
            (User.full_name.contains(search)) |
            (User.student_id.contains(search))
        ).filter_by(role='student').paginate(page=page, per_page=10)
    else:
        users = User.query.filter_by(role='student').order_by(User.username).paginate(page=page, per_page=10)
    
    return render_template('admin/users.html', users=users, search=search)

@app.route('/admin/users/add', methods=['POST'])
def add_user():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    full_name = request.form.get('full_name')
    student_id = request.form.get('student_id')
    
    # Check if username or email already exists
    if User.query.filter_by(username=username).first():
        flash('Username already exists', 'danger')
        return redirect(url_for('admin_users'))
    
    if User.query.filter_by(email=email).first():
        flash('Email already exists', 'danger')
        return redirect(url_for('admin_users'))
    
    if student_id and User.query.filter_by(student_id=student_id).first():
        flash('Student ID already exists', 'danger')
        return redirect(url_for('admin_users'))
    
    new_user = User(
        username=username,
        email=email,
        password=generate_password_hash(password, method='sha256'),
        role='student',
        full_name=full_name,
        student_id=student_id
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    flash('User added successfully', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/delete/<int:id>')
def delete_user(id):
    if id == session['user_id']:
        flash('You cannot delete your own account', 'danger')
        return redirect(url_for('admin_users'))
    
    user = User.query.get_or_404(id)
    
    # Check if user has borrowed books
    borrowed_count = Transaction.query.filter_by(user_id=id, status='borrowed').count()
    if borrowed_count > 0:
        flash('Cannot delete user with borrowed books', 'danger')
        return redirect(url_for('admin_users'))
    
    # Delete transactions related to this user
    Transaction.query.filter_by(user_id=id).delete()
    
    db.session.delete(user)
    db.session.commit()
    
    flash('User deleted successfully', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/transactions')
def admin_transactions():
    status = request.args.get('status', 'all')
    page = request.args.get('page', 1, type=int)
    
    if status == 'borrowed':
        transactions = Transaction.query.filter_by(status='borrowed').order_by(Transaction.issue_date.desc()).paginate(page=page, per_page=10)
    elif status == 'returned':
        transactions = Transaction.query.filter_by(status='returned').order_by(Transaction.return_date.desc()).paginate(page=page, per_page=10)
    elif status == 'overdue':
        transactions = Transaction.query.filter(
            Transaction.due_date < datetime.utcnow(),
            Transaction.status == 'borrowed'
        ).order_by(Transaction.due_date).paginate(page=page, per_page=10)
    else:
        transactions = Transaction.query.order_by(Transaction.issue_date.desc()).paginate(page=page, per_page=10)
    
    return render_template('admin/transactions.html', transactions=transactions, status=status)

@app.route('/admin/transactions/issue', methods=['POST'])
def issue_book():
    student_id = request.form.get('student_id')
    isbn = request.form.get('isbn')
    
    user = User.query.filter((User.student_id == student_id) | (User.username == student_id)).first()
    if not user:
        flash('Student not found', 'danger')
        return redirect(url_for('admin_transactions'))
    
    book = Book.query.filter_by(isbn=isbn).first()
    if not book:
        flash('Book not found', 'danger')
        return redirect(url_for('admin_transactions'))
    
    if book.available <= 0:
        flash('No copies of this book available', 'danger')
        return redirect(url_for('admin_transactions'))
    
    # Check if user already has this book borrowed
    existing_borrow = Transaction.query.filter_by(
        user_id=user.id,
        book_id=book.id,
        status='borrowed'
    ).first()
    
    if existing_borrow:
        flash('This student has already borrowed this book', 'danger')
        return redirect(url_for('admin_transactions'))
    
    # Create transaction
    new_transaction = Transaction(
        book_id=book.id,
        user_id=user.id,
        due_date=datetime.utcnow() + timedelta(days=14)
    )
    
    # Update book availability
    book.available -= 1
    
    db.session.add(new_transaction)
    db.session.commit()
    
    flash('Book issued successfully', 'success')
    return redirect(url_for('admin_transactions'))

@app.route('/admin/transactions/return/<int:id>')
def return_book(id):
    transaction = Transaction.query.get_or_404(id)
    
    if transaction.status == 'returned':
        flash('This book is already returned', 'info')
        return redirect(url_for('admin_transactions'))
    
    # Update transaction
    transaction.status = 'returned'
    transaction.return_date = datetime.utcnow()
    
    # Calculate fine if overdue
    if datetime.utcnow() > transaction.due_date:
        transaction.fine_amount = calculate_fine(transaction.due_date)
    
    # Update book availability
    book = Book.query.get(transaction.book_id)
    book.available += 1
    
    db.session.commit()
    
    flash('Book returned successfully', 'success')
    return redirect(url_for('admin_transactions'))

# Student Routes
@app.route('/student/dashboard')
def student_dashboard():
    user = User.query.get(session['user_id'])
    
    # Get borrowed books
    borrowed_books = Transaction.query.filter_by(
        user_id=user.id,
        status='borrowed'
    ).order_by(Transaction.due_date).all()
    
    # Calculate overdue books
    overdue_books = [t for t in borrowed_books if t.due_date < datetime.utcnow()]
    
    # Get recently borrowed books
    recent_transactions = Transaction.query.filter_by(
        user_id=user.id
    ).order_by(Transaction.issue_date.desc()).limit(5).all()
    
    return render_template('student/dashboard.html', 
                         user=user,
                         borrowed_books=borrowed_books,
                         overdue_books=overdue_books,
                         recent_transactions=recent_transactions)

@app.route('/student/browse')
def browse_books():
    search = request.args.get('search', '')
    category = request.args.get('category', 'all')
    page = request.args.get('page', 1, type=int)
    
    query = Book.query
    
    if search:
        query = query.filter(
            (Book.title.contains(search)) | 
            (Book.author.contains(search)) |
            (Book.isbn.contains(search))
        )
    
    if category != 'all':
        query = query.filter_by(category=category)
    
    books = query.order_by(Book.title).paginate(page=page, per_page=10)
    
    # Get all categories for filter dropdown
    categories = db.session.query(Book.category.distinct()).filter(Book.category.isnot(None)).all()
    categories = [c[0] for c in categories]
    
    return render_template('student/browse.html', books=books, search=search, category=category, categories=categories)

@app.route('/student/borrowed')
def borrowed_books():
    user = User.query.get(session['user_id'])
    
    # Get all borrowed books
    transactions = Transaction.query.filter_by(
        user_id=user.id,
        status='borrowed'
    ).order_by(Transaction.due_date).all()
    
    # Calculate fines for overdue books
    for t in transactions:
        if t.due_date < datetime.utcnow():
            t.fine_amount = calculate_fine(t.due_date)
    
    return render_template('student/borrowed.html', transactions=transactions)

@app.route('/student/profile', methods=['GET', 'POST'])
def student_profile():
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not check_password_hash(user.password, current_password):
            flash('Current password is incorrect', 'danger')
        elif new_password != confirm_password:
            flash('New passwords do not match', 'danger')
        else:
            user.password = generate_password_hash(new_password, method='sha256')
            db.session.commit()
            flash('Password updated successfully', 'success')
        
        return redirect(url_for('student_profile'))
    
    # Get borrowing history
    borrowing_history = Transaction.query.filter_by(
        user_id=user.id
    ).order_by(Transaction.issue_date.desc()).all()
    
    return render_template('student/profile.html', user=user, borrowing_history=borrowing_history)

# API Routes
@app.route('/api/books/available/<isbn>')
def check_book_available(isbn):
    book = Book.query.filter_by(isbn=isbn).first()
    if not book:
        return jsonify({'available': False, 'message': 'Book not found'})
    
    return jsonify({
        'available': book.available > 0,
        'quantity': book.available,
        'title': book.title,
        'author': book.author
    })

@app.route('/api/transactions/stats')
def transaction_stats():
    # Last 30 days data for chart
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Issues per day
    issues = db.session.query(
        db.func.date(Transaction.issue_date).label('date'),
        db.func.count(Transaction.id).label('count')
    ).filter(Transaction.issue_date >= thirty_days_ago).group_by('date').all()
    
    # Returns per day
    returns = db.session.query(
        db.func.date(Transaction.return_date).label('date'),
        db.func.count(Transaction.id).label('count')
    ).filter(Transaction.return_date >= thirty_days_ago).group_by('date').all()
    
    # Format data for chart
    dates = [(thirty_days_ago + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(31)]
    
    issue_data = {i.date.strftime('%Y-%m-%d'): i.count for i in issues}
    return_data = {r.date.strftime('%Y-%m-%d'): r.count for r in returns}
    
    chart_data = {
        'labels': dates,
        'datasets': [
            {
                'label': 'Books Issued',
                'data': [issue_data.get(d, 0) for d in dates],
                'backgroundColor': 'rgba(54, 162, 235, 0.5)',
                'borderColor': 'rgba(54, 162, 235, 1)',
                'borderWidth': 1
            },
            {
                'label': 'Books Returned',
                'data': [return_data.get(d, 0) for d in dates],
                'backgroundColor': 'rgba(75, 192, 192, 0.5)',
                'borderColor': 'rgba(75, 192, 192, 1)',
                'borderWidth': 1
            }
        ]
    }
    
    return jsonify(chart_data)

if __name__ == '__main__':
    app.run(debug=True)