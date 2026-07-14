import sqlite3
import os
from typing import List, Dict, Any, Optional
from config import settings

class MetricsStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path if db_path is not None else settings.METRICS_DB_PATH
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # Check if UNIQUE constraint has source_file or not.
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='metrics'")
            row = cursor.fetchone()
            if row:
                sql = row[0]
                if "source_file" in sql and "UNIQUE" in sql and "source_file" in sql.split("UNIQUE")[-1]:
                    # 1. Load all existing metrics
                    cursor.execute("SELECT company, year, metric_key, metric_label, value, unit, source_file, page FROM metrics")
                    all_rows = cursor.fetchall()
                    
                    # 2. Drop table
                    cursor.execute("DROP TABLE metrics")
                    
                    # 3. Re-create table with new constraint
                    cursor.execute("""
                        CREATE TABLE metrics (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            company TEXT,
                            year TEXT,
                            metric_key TEXT,        -- canonical taxonomy key
                            metric_label TEXT,       -- as reported
                            value REAL,
                            unit TEXT,
                            source_file TEXT,
                            page TEXT,
                            UNIQUE(company, year, metric_key) ON CONFLICT REPLACE
                        );
                    """)
                    
                    # 4. Re-insert rows (automatically resolving duplicates)
                    # We sort them so report.xml comes first, and real reports override them.
                    sorted_rows = sorted(all_rows, key=lambda r: (1 if r[6] == 'report.xml' else 0))
                    cursor.executemany("""
                        INSERT INTO metrics (company, year, metric_key, metric_label, value, unit, source_file, page)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, sorted_rows)
            else:
                # Table does not exist, create it with new constraint
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
                        UNIQUE(company, year, metric_key) ON CONFLICT REPLACE
                    );
                """)
                
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_lookup 
                ON metrics(company, year, metric_key);
            """)
            conn.commit()
        finally:
            conn.close()

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
        # Percentage check
        from src.processing.metric_taxonomy import METRIC_TAXONOMY
        is_pct = False
        if metric_key in METRIC_TAXONOMY:
            is_pct = METRIC_TAXONOMY[metric_key].get("unit") == "%"
        else:
            is_pct = metric_key.endswith("_pct") or "_pct" in metric_key or "_share" in metric_key or "_ratio" in metric_key

        if is_pct and (value < 0.0 or value > 100.0):
            import logging
            logging.getLogger(__name__).warning(
                f"Rejected inserting percentage metric '{metric_key}' with out-of-bounds value: {value} (company: {company}, year: {year})"
            )
            return

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM metrics 
                WHERE LOWER(company) = LOWER(?) AND year = ? AND metric_key = ?
            """, (company, year, metric_key))
            row = cursor.fetchone()
            if row:
                cursor.execute("""
                    UPDATE metrics 
                    SET value = ?, unit = ?, source_file = ?, page = ?, metric_label = ?
                    WHERE id = ?
                """, (value, unit, source_file, str(page), metric_label, row[0]))
            else:
                cursor.execute("""
                    INSERT INTO metrics (company, year, metric_key, metric_label, value, unit, source_file, page)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (company, year, metric_key, metric_label, value, unit, source_file, str(page)))
            conn.commit()
        finally:
            conn.close()

    def save_metrics_batch(self, metrics_list: List[Dict[str, Any]]):
        if not metrics_list:
            return
        
        valid_metrics = []
        from src.processing.metric_taxonomy import METRIC_TAXONOMY
        for m in metrics_list:
            key = m.get("metric_key")
            val = m.get("value")
            is_pct = False
            if key in METRIC_TAXONOMY:
                is_pct = METRIC_TAXONOMY[key].get("unit") == "%"
            elif key:
                is_pct = key.endswith("_pct") or "_pct" in key or "_share" in key or "_ratio" in key
            
            if is_pct and val is not None and (val < 0.0 or val > 100.0):
                import logging
                logging.getLogger(__name__).warning(
                    f"Rejected batch inserting percentage metric '{key}' with out-of-bounds value: {val} (company: {m.get('company')}, year: {m.get('year')})"
                )
                continue
            valid_metrics.append(m)

        if not valid_metrics:
            return

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            for m in valid_metrics:
                comp = m.get("company")
                yr = m.get("year")
                k = m.get("metric_key")
                val = m.get("value")
                lbl = m.get("metric_label")
                un = m.get("unit")
                src = m.get("source_file")
                pg = str(m.get("page", ""))
                
                cursor.execute("""
                    SELECT id FROM metrics 
                    WHERE LOWER(company) = LOWER(?) AND year = ? AND metric_key = ?
                """, (comp, yr, k))
                row = cursor.fetchone()
                if row:
                    cursor.execute("""
                        UPDATE metrics 
                        SET value = ?, unit = ?, source_file = ?, page = ?, metric_label = ?
                        WHERE id = ?
                    """, (val, un, src, pg, lbl, row[0]))
                else:
                    cursor.execute("""
                        INSERT INTO metrics (company, year, metric_key, metric_label, value, unit, source_file, page)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (comp, yr, k, lbl, val, un, src, pg))
            conn.commit()
        finally:
            conn.close()

    def get_metric(self, company: str, year: str, metric_key: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT company, year, metric_key, metric_label, value, unit, source_file, page
                FROM metrics
                WHERE LOWER(company) = LOWER(?) AND year = ? AND metric_key = ?
            """, (company, year, metric_key))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_metric_for_all_companies(self, year: str, metric_key: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT company, year, metric_key, metric_label, value, unit, source_file, page
                FROM metrics
                WHERE year = ? AND metric_key = ?
            """, (year, metric_key))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_all_companies(self) -> List[str]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT company FROM metrics ORDER BY company")
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_company_years(self, company: str) -> List[str]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT year FROM metrics WHERE LOWER(company) = LOWER(?) ORDER BY year DESC", (company,))
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_most_recent_year_for_metric(self, company: str, metric_key: str) -> Optional[str]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT year FROM metrics 
                WHERE LOWER(company) = LOWER(?) AND metric_key = ? 
                ORDER BY year DESC LIMIT 1
            """, (company, metric_key))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def get_company_metrics(self, company: str, year: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT company, year, metric_key, metric_label, value, unit, source_file, page
                FROM metrics
                WHERE LOWER(company) = LOWER(?) AND year = ?
            """, (company, year))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_metrics_for_companies(self, companies: List[str], metric_keys: List[str]) -> List[Dict[str, Any]]:
        if not companies or not metric_keys:
            return []
        placeholders_companies = ",".join(["?"] * len(companies))
        placeholders_keys = ",".join(["?"] * len(metric_keys))
        params = [c.lower() for c in companies] + metric_keys
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT company, year, metric_key, metric_label, value, unit, source_file, page
                FROM metrics
                WHERE LOWER(company) IN ({placeholders_companies}) AND metric_key IN ({placeholders_keys})
            """, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def clear_company_metrics(self, company: str, year: str, source_file: Optional[str] = None):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            if source_file:
                cursor.execute(
                    "DELETE FROM metrics WHERE LOWER(company) = LOWER(?) AND year = ? AND LOWER(source_file) = LOWER(?)",
                    (company, year, os.path.basename(source_file))
                )
            else:
                cursor.execute("DELETE FROM metrics WHERE LOWER(company) = LOWER(?) AND year = ?", (company, year))
            conn.commit()
        finally:
            conn.close()

    def get_xml_metrics(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT metric_key, metric_label, value, unit, company, year, source_file
                FROM metrics
                WHERE LOWER(source_file) LIKE '%.xml'
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
