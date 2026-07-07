import sqlite3
from typing import List, Dict, Any, Optional
from config import settings

class MetricsStore:
    def __init__(self, db_path: str = settings.METRICS_DB_PATH):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company TEXT,
                    year TEXT,
                    metric_key TEXT,        -- canonical taxonomy key
                    metric_label TEXT,       -- as reported
                    value REAL,
                    unit TEXT,
                    source_file TEXT,
                    page TEXT,
                    UNIQUE(company, year, metric_key, source_file) ON CONFLICT REPLACE
                );
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_lookup 
                ON metrics(company, year, metric_key);
            """)
            conn.commit()

    def save_metric(
        self,
        company: str,
        year: str,
        metric_key: str,
        metric_label: str,
        value: float,
        unit: str,
        source_file: str,
        page: str
    ):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO metrics (company, year, metric_key, metric_label, value, unit, source_file, page)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (company, year, metric_key, metric_label, value, unit, source_file, str(page)))
            conn.commit()

    def save_metrics_batch(self, metrics_list: List[Dict[str, Any]]):
        if not metrics_list:
            return
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT INTO metrics (company, year, metric_key, metric_label, value, unit, source_file, page)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    m.get("company"),
                    m.get("year"),
                    m.get("metric_key"),
                    m.get("metric_label"),
                    m.get("value"),
                    m.get("unit"),
                    m.get("source_file"),
                    str(m.get("page", ""))
                )
                for m in metrics_list
            ])
            conn.commit()

    def get_metric(self, company: str, year: str, metric_key: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT company, year, metric_key, metric_label, value, unit, source_file, page
                FROM metrics
                WHERE LOWER(company) = LOWER(?) AND year = ? AND metric_key = ?
            """, (company, year, metric_key))
            return [dict(row) for row in cursor.fetchall()]

    def get_all_companies(self) -> List[str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT company FROM metrics ORDER BY company")
            return [row[0] for row in cursor.fetchall()]

    def get_company_years(self, company: str) -> List[str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT year FROM metrics WHERE LOWER(company) = LOWER(?) ORDER BY year DESC", (company,))
            return [row[0] for row in cursor.fetchall()]

    def get_company_metrics(self, company: str, year: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT company, year, metric_key, metric_label, value, unit, source_file, page
                FROM metrics
                WHERE LOWER(company) = LOWER(?) AND year = ?
            """, (company, year))
            return [dict(row) for row in cursor.fetchall()]

    def get_metrics_for_companies(self, companies: List[str], metric_keys: List[str]) -> List[Dict[str, Any]]:
        if not companies or not metric_keys:
            return []
        placeholders_companies = ",".join(["?"] * len(companies))
        placeholders_keys = ",".join(["?"] * len(metric_keys))
        params = [c.lower() for c in companies] + metric_keys
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT company, year, metric_key, metric_label, value, unit, source_file, page
                FROM metrics
                WHERE LOWER(company) IN ({placeholders_companies}) AND metric_key IN ({placeholders_keys})
            """, params)
            return [dict(row) for row in cursor.fetchall()]

    def clear_company_metrics(self, company: str, year: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM metrics WHERE LOWER(company) = LOWER(?) AND year = ?", (company, year))
            conn.commit()
