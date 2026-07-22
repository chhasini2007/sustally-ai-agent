import sqlite3

def check_db():
    conn = sqlite3.connect("data/metrics.db")
    cursor = conn.cursor()
    
    print("--- Infosys Limited metrics ---")
    cursor.execute("SELECT year, metric_key, value, unit, source_file FROM metrics WHERE company = 'Infosys Limited' ORDER BY year, metric_key")
    for row in cursor.fetchall():
        print(row)
        
    print("\n--- TCS metrics ---")
    cursor.execute("SELECT year, metric_key, value, unit, source_file FROM metrics WHERE company = 'Tata Consultancy Services Limited' ORDER BY year, metric_key")
    for row in cursor.fetchall():
        print(row)

    conn.close()

if __name__ == "__main__":
    check_db()
