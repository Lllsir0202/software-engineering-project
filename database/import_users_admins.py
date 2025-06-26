# import_users_admins.py

import json
from datetime import datetime
from werkzeug.security import generate_password_hash  # 用于安全加密密码

import sys
sys.path.append('..')  # Add parent directory to path for imports

from app import app
from database.models import db, User

def import_users(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        users = json.load(f)
        for u in users:
            existing_user = User.query.filter_by(username=u['username']).first()
            if existing_user:
                print(f"用户 {u['username']} 已存在，跳过")
                continue
            user = User(
                username=u['username'],
                email=u['email'],
                password=generate_password_hash(u['password'],method='pbkdf2:sha256'),  # 加密存储
                role='user',  # set role as user
                created_at=datetime.now()
            )
            db.session.add(user)
        db.session.commit()
        print("users succeed to import")

def import_admins(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        users = json.load(f)
        for u in users:
            existing_user = User.query.filter_by(username=u['username']).first()
            if existing_user:
                print(f"用户 {u['username']} 已存在，跳过")
                continue
            user = User(
                username=u['username'],
                email=u['email'],
                password=generate_password_hash(u['password'],method='pbkdf2:sha256'),  # 加密存储
                role='admin',  # set role as admin
                created_at=datetime.now()
            )
            db.session.add(user)
        db.session.commit()
        print("admins succeed to import")

if __name__ == "__main__":
    with app.app_context():
        import_users("../static/user.json")
        import_admins("../static/admin.json")
        print("Users and admins imported successfully.")