import sqlite3
import os
import hashlib
from datetime import datetime
from typing import Optional, Tuple
from config import settings

class UsersStore:
    def __init__(self, db_path: str = None):
        if db_path is None:
            from pathlib import Path
            db_path = str(Path(settings.DATA_DIR) / "users.db")
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def hash_password(self, password: str) -> str:
        salt = os.urandom(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        return f"{salt.hex()}:{pwd_hash.hex()}"

    def verify_password(self, stored_hash: str, provided_password: str) -> bool:
        try:
            salt_hex, hash_hex = stored_hash.split(":")
            salt = bytes.fromhex(salt_hex)
            expected_hash = bytes.fromhex(hash_hex)
            pwd_hash = hashlib.pbkdf2_hmac(
                'sha256',
                provided_password.encode('utf-8'),
                salt,
                100000
            )
            return pwd_hash == expected_hash
        except Exception:
            return False

    def create_user(self, username: str, password_raw: str) -> Tuple[bool, str]:
        username = username.strip()
        if not username:
            return False, "Username cannot be empty."
        if len(password_raw) < 8:
            return False, "Password must be at least 8 characters long."
            
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (username,))
            if cursor.fetchone():
                return False, "Username is already taken."
                
            pwd_hash = self.hash_password(password_raw)
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO users (username, password_hash, created_at)
                VALUES (?, ?, ?)
            """, (username, pwd_hash, now))
            conn.commit()
            return True, "User registered successfully."
        except Exception as e:
            return False, f"Database error: {str(e)}"
        finally:
            conn.close()

    def authenticate_user(self, username: str, password_raw: str) -> bool:
        username = username.strip()
        if not username or not password_raw:
            return False
            
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM users WHERE LOWER(username) = LOWER(?)", (username,))
            row = cursor.fetchone()
            if not row:
                return False
            stored_hash = row[0]
            return self.verify_password(stored_hash, password_raw)
        except Exception:
            return False
        finally:
            conn.close()
