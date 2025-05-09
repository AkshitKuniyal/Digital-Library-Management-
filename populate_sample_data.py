import random
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash
from app import app, db
from app import User, Book, Transaction

def create_sample_data():
    with app.app_context():
        # Clear existing data
        db.drop_all()
        db.create_all()

        # Sample Users
        users = []
        for i in range(1, 11):
            user = User(
                username=f'user{i}',
                email=f'user{i}@example.com',
                password=generate_password_hash(f'password{i}'),
                role='admin' if i == 1 else 'student',
                full_name=f'User {i}',
                student_id=f'STU{1000 + i}' if i > 1 else None
            )
            users.append(user)
            db.session.add(user)
        
        # Commit users first to get their IDs
        db.session.commit()

        # Sample Books
        books = []
        genres = ['Fiction', 'Non-Fiction', 'Science', 'History', 'Biography', 'Technology']
        publishers = ['Penguin', 'HarperCollins', 'Random House', 'Macmillan', 'Hachette']
        
        for i in range(1, 11):
            book = Book(
                title=f'Sample Book {i}',
                author=f'Author {i}',
                isbn=f'978{random.randint(1000000000, 9999999999)}',
                publisher=random.choice(publishers),
                category=random.choice(genres),
                description=f'This is a sample description for Book {i}',
                quantity=random.randint(1, 5),
                available=random.randint(1, 5),
                cover_image=f'book_cover_{i}.jpg' if i % 2 == 0 else None,
                added_by=1  # First user is admin
            )
            books.append(book)
            db.session.add(book)
        
        # Commit books to get their IDs
        db.session.commit()

        # Sample Transactions
        statuses = ['borrowed', 'returned', 'overdue']
        for i in range(1, 11):
            # Get timezone-aware current time
            now = datetime.now(timezone.utc)
            
            # Random dates within last 30 days
            issue_date = now - timedelta(days=random.randint(1, 30))
            due_date = issue_date + timedelta(days=14)
            
            # 50% chance of being returned
            if random.choice([True, False]):
                return_date = issue_date + timedelta(days=random.randint(1, 14))
                status = 'returned'
            else:
                return_date = None
                status = 'overdue' if due_date < now else 'borrowed'
            
            # Ensure we have valid book and user IDs
            book_id = books[i-1].id
            user_id = users[i-1].id
            
            transaction = Transaction(
                book_id=book_id,
                user_id=user_id,
                issue_date=issue_date,
                return_date=return_date,
                due_date=due_date,
                status=status,
                fine_amount=random.uniform(0, 10) if status == 'overdue' else 0.0
            )
            db.session.add(transaction)
        
        db.session.commit()
        print("Successfully populated database with sample data!")

if __name__ == '__main__':
    create_sample_data()