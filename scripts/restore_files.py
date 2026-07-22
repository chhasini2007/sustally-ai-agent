import os
import shutil
from pathlib import Path

def restore_files():
    backup_dir = Path("data/incoming_xml_backup")
    inc_dir = Path("data/incoming_xml")
    
    if not backup_dir.exists():
        print("Backup directory does not exist. Nothing to restore.")
        return
        
    restored_count = 0
    for file in backup_dir.iterdir():
        if file.is_file():
            shutil.move(str(file), str(inc_dir / file.name))
            restored_count += 1
            
    print(f"Restored {restored_count} files back to incoming_xml.")
    try:
        os.rmdir(backup_dir)
        print("Removed backup directory.")
    except Exception as e:
        print(f"Could not remove backup directory: {e}")

if __name__ == "__main__":
    restore_files()
