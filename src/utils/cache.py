import sqlite3
import hashlib
from typing import Optional
from config import settings

class QueryCache:
    def __init__(self, db_path: str = settings.CACHE_DB_PATH):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS query_cache (
                    company TEXT,
                    year TEXT,
                    query_hash TEXT,
                    response TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(company, year, query_hash)
                );
            """)
            conn.commit()

    def _get_hash(self, query_text: str) -> str:
        normalized = query_text.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def get_cached_answer(self, company: str, year: str, query_text: str) -> Optional[str]:
        q_hash = self._get_hash(query_text)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT response FROM query_cache 
                WHERE LOWER(company) = LOWER(?) AND year = ? AND query_hash = ?
            """, (company, year, q_hash))
            row = cursor.fetchone()
            if row:
                return row[0]
        return None

    def set_cached_answer(self, company: str, year: str, query_text: str, response: str):
        q_hash = self._get_hash(query_text)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO query_cache (company, year, query_hash, response, timestamp)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (company, year, q_hash, response))
            conn.commit()

    def clear_cache(self, company: Optional[str] = None, year: Optional[str] = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if company and year:
                cursor.execute("DELETE FROM query_cache WHERE LOWER(company) = LOWER(?) AND year = ?", (company, year))
            elif company:
                cursor.execute("DELETE FROM query_cache WHERE LOWER(company) = LOWER(?)", (company,))
            else:
                cursor.execute("DELETE FROM query_cache")
            conn.commit()
