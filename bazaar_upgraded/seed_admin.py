"""
Run this script once after setting up the database to create an admin user.
Usage:  python seed_admin.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.models import db, Member, Student, Authentication
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

ADMIN_NAME     = "Admin"
ADMIN_EMAIL    = "adminbazaar@iitgn.ac.in"
ADMIN_PASSWORD = "admin123"   # change after first login!

def seed():
    app = create_app()
    bcrypt.init_app(app)

    with app.app_context():
        if Member.query.filter_by(email=ADMIN_EMAIL).first():
            print(f"[!] Admin already exists: {ADMIN_EMAIL}")
            return

        member = Member(name=ADMIN_NAME, email=ADMIN_EMAIL, phone="0000000000", role="admin")
        db.session.add(member)
        db.session.flush()

        student = Student(member_id=member.member_id, college_name="CampusTrade HQ")
        db.session.add(student)

        pw_hash = bcrypt.generate_password_hash(ADMIN_PASSWORD).decode("utf-8")
        auth = Authentication(member_id=member.member_id, password_hash=pw_hash)
        db.session.add(auth)

        db.session.commit()
        print(f"[+] Admin created!")
        print(f"    Email   : {ADMIN_EMAIL}")
        print(f"    Password: {ADMIN_PASSWORD}")
        print(f"    ⚠️  Change the password after first login.")

if __name__ == "__main__":
    seed()
