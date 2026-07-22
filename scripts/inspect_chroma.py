import sqlite3

def check_stuck():
    conn = sqlite3.connect("vector_db/chroma.sqlite3")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM embeddings_queue LIMIT 5")
    queue_ids = [r[0] for r in cursor.fetchall()]
    
    print("Checking if queue IDs exist in 'embeddings' table:")
    for q_id in queue_ids:
        cursor.execute("SELECT COUNT(*) FROM embeddings WHERE id = ?", (q_id,))
        count = cursor.fetchone()[0]
        print(f"ID: {q_id} | Exist Count in embeddings: {count}")
    conn.close()

if __name__ == "__main__":
    check_stuck()
