import sqlite3

def clear_queue():
    db_path = "vector_db/chroma.sqlite3"
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        
        # Check current count
        cursor.execute("SELECT COUNT(*) FROM embeddings_queue")
        before = cursor.fetchone()[0]
        print(f"Queue count before: {before}")
        
        # Clear queue
        cursor.execute("DELETE FROM embeddings_queue")
        conn.commit()
        
        # Check count after
        cursor.execute("SELECT COUNT(*) FROM embeddings_queue")
        after = cursor.fetchone()[0]
        print(f"Queue count after: {after}")
        print("Successfully cleared the embeddings queue!")
    except Exception as e:
        print(f"Failed to clear queue: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    clear_queue()
