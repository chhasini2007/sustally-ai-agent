import os
import shutil
import hashlib
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any

from config import settings
from src.ingestion.bulk_xml_importer import detect_metadata_from_xml, get_unique_filename
from src.ingestion.document_manager import DocumentManager

# Setup logger
logger = logging.getLogger("xml_importer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def import_xml_reports() -> Dict[str, int]:
    """
    Scans data/incoming_xml/ for XML ESG reports, parses metadata, validates XML structure,
    calculates SHA256 hashes, skips indexed files, moves files to raw_reports,
    and runs ingestion to index chunks into ChromaDB/SQLite.
    """
    incoming_dir = Path(settings.INCOMING_XML_DIR)
    raw_dir = Path(settings.RAW_DIR)
    unsorted_dir = raw_dir / "_unsorted"

    stats = {
        "scanned": 0,
        "success": 0,
        "indexed": 0,
        "unsorted": 0,
        "failed": 0
    }

    if not incoming_dir.exists():
        logger.error(f"Incoming XML directory does not exist: {incoming_dir}")
        return stats

    # Find all XML files in incoming_dir (non-recursive, case-insensitive extension check)
    xml_files = []
    for file in incoming_dir.iterdir():
        if file.is_file() and file.suffix.lower() == ".xml":
            xml_files.append(file)

    stats["scanned"] = len(xml_files)
    logger.info(f"Found {stats['scanned']} XML files in {incoming_dir}")

    document_manager = DocumentManager()
    document_manager.load_index()

    for file_path in xml_files:
        logger.info(f"Processing: {file_path.name}")
        
        # 1. Validate XML structure
        try:
            ET.parse(file_path)
        except Exception as e:
            logger.error(f"Invalid XML structure for '{file_path.name}': {e}")
            stats["failed"] += 1
            # Move to unsorted
            unsorted_dir.mkdir(parents=True, exist_ok=True)
            target_path = get_unique_filename(unsorted_dir, file_path.name)
            try:
                shutil.copy(str(file_path), str(target_path))
                os.remove(file_path)
                logger.info(f"Moved invalid XML file to: {target_path}")
            except Exception as move_err:
                logger.error(f"Failed to move invalid XML file '{file_path.name}': {move_err}")
            continue

        # 2. Parse company and year
        company, year, error_reason = detect_metadata_from_xml(file_path)
        
        # 3. Calculate SHA256 hash
        try:
            hasher = hashlib.sha256()
            with open(file_path, "rb") as f:
                buf = f.read(65536)
                while len(buf) > 0:
                    hasher.update(buf)
                    buf = f.read(65536)
            file_hash = hasher.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for '{file_path.name}': {e}")
            stats["failed"] += 1
            continue

        # 4. Skip files already indexed (checking document_index.json)
        is_indexed = False
        for path, val in document_manager.index.items():
            if val.get("file_hash") == file_hash:
                is_indexed = True
                break

        if is_indexed:
            logger.info(f"[SKIPPED] Already indexed: {file_path.name}")
            stats["indexed"] += 1
            continue

        # If metadata is unclear
        if error_reason or not company or not year:
            logger.warning(f"Unclear metadata for '{file_path.name}': {error_reason or 'missing company/year'}")
            stats["unsorted"] += 1
            unsorted_dir.mkdir(parents=True, exist_ok=True)
            target_path = get_unique_filename(unsorted_dir, file_path.name)
            try:
                shutil.copy(str(file_path), str(target_path))
                os.remove(file_path)
                logger.info(f"Moved unclear file to: {target_path}")
            except Exception as move_err:
                logger.error(f"Failed to move unclear file '{file_path.name}': {move_err}")
            continue

        # 5. Move valid XML files to raw_reports/<company>/<year>/
        target_company_year_dir = raw_dir / company / year
        target_company_year_dir.mkdir(parents=True, exist_ok=True)
        target_path = get_unique_filename(target_company_year_dir, file_path.name)

        try:
            shutil.copy(str(file_path), str(target_path))
        except Exception as copy_err:
            logger.error(f"Failed to copy '{file_path.name}' to raw reports: {copy_err}")
            stats["failed"] += 1
            continue

        # 6. Ingest file into database/indexes
        try:
            logger.info(f"Ingesting '{target_path.name}' into vector database...")
            document_manager.load_index() # reload index to ensure freshness
            ingest_result = document_manager.ingest_new_reports(target_files=[str(target_path)])
            
            if ingest_result.get("processed", 0) > 0:
                # Successfully ingested, now safe to delete source file
                os.remove(file_path)
                logger.info(f"Successfully imported: {file_path.name} -> {target_path}")
                stats["success"] += 1
            else:
                logger.error(f"Ingestion yielded 0 processed files for: {target_path}")
                # Rollback copy if failed
                if target_path.exists():
                    os.remove(target_path)
                stats["failed"] += 1
        except Exception as ingest_err:
            logger.error(f"Ingestion failed for '{file_path.name}': {ingest_err}")
            if target_path.exists():
                os.remove(target_path)
            stats["failed"] += 1

    return stats
