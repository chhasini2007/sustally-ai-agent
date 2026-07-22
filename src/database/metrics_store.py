import sqlite3
import os
from typing import List, Dict, Any, Optional
import logging
from config import settings

logger = logging.getLogger(__name__)

METRIC_ALIASES = {
    "scope1_emissions": [
        "TotalScope1Emissions",
        "Scope1Emissions",
        "Scope 1 Emissions",
        "scope1_emissions_tco2e",
        "scope1_emissions"
    ],
    "scope2_emissions": [
        "TotalScope2Emissions",
        "Scope2Emissions",
        "Scope 2 Emissions",
        "scope2_emissions_tco2e",
        "scope2_emissions"
    ],
    "scope3_emissions": [
        "TotalScope3Emissions",
        "Scope3Emissions",
        "Scope 3 Emissions",
        "scope3_emissions_tco2e",
        "scope3_emissions"
    ],
    "water_consumption": [
        "TotalVolumeOfWaterConsumption",
        "Water Consumption",
        "water_consumption_kl",
        "water_consumption"
    ],
    "water_consumption_kl": [
        "TotalVolumeOfWaterConsumption",
        "Water Consumption",
        "water_consumption_kl",
        "water_consumption"
    ],
    "waste_generated": [
        "TotalWasteGenerated",
        "waste_generation_tonnes",
        "waste_generated"
    ],
    "waste_generation_tonnes": [
        "TotalWasteGenerated",
        "waste_generation_tonnes",
        "waste_generated"
    ],
    "female_percentage": [
        "PercentageOfGrossWagesPaidToFemaleToTotalWagesPaid",
        "PercentageOfEmployeesOrWorkersIncludingDifferentlyAbled",
        "Female Workforce %",
        "Women Employees %",
        "female_employee_headcount_share_pct",
        "female_percentage"
    ],
    "female_employee_headcount_share_pct": [
        "PercentageOfGrossWagesPaidToFemaleToTotalWagesPaid",
        "PercentageOfEmployeesOrWorkersIncludingDifferentlyAbled",
        "Female Workforce %",
        "Women Employees %",
        "female_employee_headcount_share_pct",
        "female_percentage"
    ],
    "female_employee_count": [
        "AverageNumberOfFemaleEmployeesOrWorkersAtTheBeginningOfTheYearAndAsAtEndOfTheYear",
        "female_employee_count"
    ],
    "total_employee_count": [
        "AverageNumberOfEmployeesOrWorkersAtTheBeginningOfTheYearAndAsAtEndOfTheYear",
        "NumberOfEmployeesCoveredAsPercentageOfTotalEmployees",
        "total_employee_count",
        "total employees",
        "employees"
    ],
    "renewable_energy_pct": [
        "TotalEnergyConsumedFromRenewableAndNonRenewableSources",
        "TotalEnergyConsumedFromRenewableSources",
        "Renewable Energy %",
        "renewable_energy_pct",
        "Calculated from: TotalEnergyConsumedFromRenewableAndNonRenewableSources",
        "Calculated from: TotalEnergyConsumedFromRenewableSources"
    ]
}

def get_all_aliases(metric_key: str) -> List[str]:
    base_key = metric_key.lower().replace("_tco2e", "").replace("_kl", "").replace("_tonnes", "")
    aliases = set()
    for key, val in METRIC_ALIASES.items():
        key_clean = key.lower().replace("_tco2e", "").replace("_kl", "").replace("_tonnes", "")
        if key_clean == base_key:
            aliases.update(val)
    if not aliases:
        aliases.add(metric_key)
    return list(aliases)

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

    def get_metric_with_aliases(self, company: Optional[str], year: Optional[str], metric_key: str, companies: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        aliases = get_all_aliases(metric_key)
        conditions = []
        params = []
        
        if company:
            conditions.append("LOWER(company) = LOWER(?)")
            params.append(company)
        elif companies:
            placeholders = ",".join(["?"] * len(companies))
            conditions.append(f"LOWER(company) IN ({placeholders})")
            params.extend([c.lower() for c in companies])
            
        if year:
            conditions.append("year = ?")
            params.append(year)
            
        placeholders_aliases = ",".join(["?"] * len(aliases))
        conditions.append(f"(metric_key IN ({placeholders_aliases}) OR metric_label IN ({placeholders_aliases}))")
        params.extend(aliases + aliases)
            
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"""
            SELECT company, year, metric_key AS metric, value, unit, source_file, page, metric_label, metric_key
            FROM metrics
            {where_clause}
        """
        
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = [dict(row) for row in cursor.fetchall()]
            
            matched = []
            for r in rows:
                r["metric_key"] = r.get("metric_key") or r.get("metric")
                matched.append(r)
                
            if not matched:
                like_conditions = []
                like_params = []
                if company:
                    like_conditions.append("LOWER(company) = LOWER(?)")
                    like_params.append(company)
                elif companies:
                    placeholders = ",".join(["?"] * len(companies))
                    like_conditions.append(f"LOWER(company) IN ({placeholders})")
                    like_params.extend([c.lower() for c in companies])
                if year:
                    like_conditions.append("year = ?")
                    like_params.append(year)
                    
                sub_clauses = []
                for alias in aliases:
                    clean = alias.split("}")[-1].replace("_", "").replace(" ", "").strip()
                    if len(clean) > 3:
                        sub_clauses.append("metric_key LIKE ? OR metric_label LIKE ?")
                        like_params.extend([f"%{clean}%", f"%{clean}%"])
                if sub_clauses:
                    like_conditions.append(f"({' OR '.join(sub_clauses)})")
                    where_clause = " WHERE " + " AND ".join(like_conditions) if like_conditions else ""
                    sql = f"""
                        SELECT company, year, metric_key AS metric, value, unit, source_file, page, metric_label, metric_key
                        FROM metrics
                        {where_clause}
                    """
                    cursor.execute(sql, like_params)
                    for row in cursor.fetchall():
                        r = dict(row)
                        r["metric_key"] = r.get("metric_key") or r.get("metric")
                        matched.append(r)
            return matched
        finally:
            conn.close()

    def get_metric(self, company: str, year: str, metric_key: str) -> List[Dict[str, Any]]:
        return self.get_metric_with_aliases(company, year, metric_key)

    def get_metric_for_all_companies(self, year: str, metric_key: str) -> List[Dict[str, Any]]:
        return self.get_metric_with_aliases(None, year, metric_key)

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
        aliases = get_all_aliases(metric_key)
        placeholders = ",".join(["?"] * len(aliases))
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT year FROM metrics 
                WHERE LOWER(company) = LOWER(?) AND (
                    metric_key IN ({placeholders}) OR
                    metric_label IN ({placeholders})
                ) 
                ORDER BY year DESC LIMIT 1
            """, [company] + aliases + aliases)
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
        results = []
        for key in metric_keys:
            rows = self.get_metric_with_aliases(None, None, key, companies=companies)
            results.extend(rows)
        return results

    def get_filtered_ranking_metrics(
        self,
        metric_key: str,
        companies: Optional[List[str]] = None,
        year: Optional[str] = None,
        threshold_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        aliases = get_all_aliases(metric_key)
        placeholders_aliases = ",".join(["?"] * len(aliases))
        
        conditions = [f"(metric_key IN ({placeholders_aliases}) OR metric_label IN ({placeholders_aliases}))"]
        params = list(aliases) + list(aliases)
        
        if year:
            conditions.append("year = ?")
            params.append(year)
            
        if companies:
            placeholders_companies = ",".join(["?"] * len(companies))
            conditions.append(f"LOWER(company) IN ({placeholders_companies})")
            params.extend([c.lower() for c in companies])
            
        if threshold_filter:
            op = threshold_filter.get("operator")
            val = threshold_filter.get("value")
            if op in [">", "<", "=", ">=", "<="]:
                conditions.append(f"value {op} ?")
                params.append(val)
                
        where_clause = " WHERE " + " AND ".join(conditions)
        sql = f"""
            SELECT company,
                   year,
                   metric_key AS metric,
                   value,
                   unit,
                   source_file,
                   page,
                   metric_label,
                   metric_key
            FROM metrics
            {where_clause}
            ORDER BY value DESC
        """
        
        logger.info(f"Generated SQL for ranking/filtering: {sql.strip()} with params {params}")
        
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = [dict(row) for row in cursor.fetchall()]
            
            if not rows:
                logger.info("Strict SQL IN returned 0 rows. Using fuzzy alias matching fallback.")
                fuzzy_rows = self.get_metric_with_aliases(None, year, metric_key, companies=companies)
                if threshold_filter:
                    op = threshold_filter.get("operator")
                    val = threshold_filter.get("value")
                    if op == ">":
                        fuzzy_rows = [r for r in fuzzy_rows if r.get("value", 0.0) > val]
                    elif op == "<":
                        fuzzy_rows = [r for r in fuzzy_rows if r.get("value", 0.0) < val]
                    elif op == "=":
                        fuzzy_rows = [r for r in fuzzy_rows if r.get("value", 0.0) == val]
                fuzzy_rows = sorted(fuzzy_rows, key=lambda r: r.get("value", 0.0), reverse=True)
                rows = fuzzy_rows
                
            return rows
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
