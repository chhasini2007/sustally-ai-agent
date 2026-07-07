import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from config import settings

class HistoryStore:
    def __init__(self, db_path: str = settings.HISTORY_DB_PATH):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 1. Charts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS charts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_key TEXT UNIQUE,
                    companies TEXT,
                    years TEXT,
                    metric_keys TEXT,
                    figure_json TEXT,
                    created_at TEXT,
                    last_used_at TEXT
                );
            """)
            
            # 2. Conversations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE,
                    created_at TEXT,
                    title TEXT
                );
            """)
            
            # 3. Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER,
                    role TEXT,
                    content TEXT,
                    lane TEXT,
                    chart_id INTEGER,
                    created_at TEXT,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id),
                    FOREIGN KEY(chart_id) REFERENCES charts(id)
                );
            """)
            
            # Indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
            """)
            
            conn.commit()

    def create_conversation(self, session_id: str, title: str) -> int:
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO conversations (session_id, created_at, title)
                VALUES (?, ?, ?)
            """, (session_id, now, title))
            conn.commit()
            
            # Return ID
            cursor.execute("SELECT id FROM conversations WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            return row[0] if row else -1

    def get_conversation_by_session(self, session_id: str) -> Optional[int]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM conversations WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            return row[0] if row else None

    def get_conversation_messages(self, conversation_id: int) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.id, m.role, m.content, m.lane, m.chart_id, m.created_at,
                       c.topic_key, c.figure_json, c.created_at as chart_created_at
                FROM messages m
                LEFT JOIN charts c ON m.chart_id = c.id
                WHERE m.conversation_id = ?
                ORDER BY m.id ASC
            """, (conversation_id,))
            rows = cursor.fetchall()
            
            messages = []
            for r in rows:
                msg = {
                    "id": r["id"],
                    "role": r["role"],
                    "content": r["content"],
                    "lane": r["lane"],
                    "chart_id": r["chart_id"],
                    "created_at": r["created_at"],
                    "topic_key": r["topic_key"],
                    "figure_json": r["figure_json"],
                    "chart_created_at": r["chart_created_at"]
                }
                messages.append(msg)
            return messages

    def get_conversations_list(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, session_id, created_at, title 
                FROM conversations 
                ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def add_message(self, conversation_id: int, role: str, content: str, lane: Optional[str] = None, chart_id: Optional[int] = None) -> int:
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (conversation_id, role, content, lane, chart_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (conversation_id, role, content, lane, chart_id, now))
            cursor.execute("""
                UPDATE conversations SET created_at = ? WHERE id = ?
            """, (now, conversation_id))
            conn.commit()
            return cursor.lastrowid

    def get_cached_chart(self, topic_key: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, topic_key, companies, years, metric_keys, figure_json, created_at, last_used_at
                FROM charts
                WHERE topic_key = ?
            """, (topic_key,))
            row = cursor.fetchone()
            if row:
                res = dict(row)
                res["companies"] = json.loads(res["companies"])
                res["years"] = json.loads(res["years"])
                res["metric_keys"] = json.loads(res["metric_keys"])
                return res
            return None

    def save_cached_chart(self, topic_key: str, companies: List[str], years: List[str], metric_keys: List[str], figure_json: str) -> int:
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO charts (topic_key, companies, years, metric_keys, figure_json, created_at, last_used_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (topic_key, json.dumps(companies), json.dumps(years), json.dumps(metric_keys), figure_json, now, now))
            conn.commit()
            return cursor.lastrowid

    def update_chart_used_time(self, chart_id: int):
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE charts SET last_used_at = ? WHERE id = ?", (now, chart_id))
            conn.commit()
