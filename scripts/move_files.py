import os
import shutil
from pathlib import Path

def move_files():
    inc_dir = Path("data/incoming_xml")
    backup_dir = Path("data/incoming_xml_backup")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    keep_files = {
        "BRSR_1477079_03072025095250_WEB.xml",
        "BRSR_1474736_30062025044052_WEB.xml",
        "BRSR_500209_1062026191217_BRSR_WebXMLFile_20260610_191246055.xml",
        "BRSR_532540_155202623553_BRSR_WebXMLFile_20260602_163936876.xml",
        "tcs_report.xml"
    }
    
    moved_to_backup = 0
    for file in inc_dir.iterdir():
        if file.is_file() and file.suffix.lower() == ".xml":
            if file.name not in keep_files:
                shutil.move(str(file), str(backup_dir / file.name))
                moved_to_backup += 1
                
    print(f"Moved {moved_to_backup} files to backup folder.")
    print("Files left in incoming_xml:")
    for file in inc_dir.iterdir():
        print(f" - {file.name}")

if __name__ == "__main__":
    move_files()
