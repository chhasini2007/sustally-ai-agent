import os
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import concurrent.futures

from config import settings
from src.ingestion.pdf_loader import PDFLoader
from src.ingestion.xml_loader import XMLLoader
from src.processing.chunker import Chunker
from src.processing.metric_extractor import MetricExtractor
from src.embeddings.embedding_manager import EmbeddingManager
from src.database.chroma_store import ChromaStore
from src.database.metrics_store import MetricsStore
from src.utils.cache import QueryCache

# Helper function that runs inside worker processes for PDF parsing
def _parse_single_file(file_info: Tuple[str, str, str, str]) -> Dict[str, Any]:
    file_path, company, year, file_type = file_info
    
    # Calculate hash
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    file_hash = hasher.hexdigest()
    
    extracted_pages = []
    extracted_tables = []
    extracted_xml_metrics = []
    
    if file_type == "pdf":
        loader = PDFLoader()
        extracted_pages, extracted_tables = loader.load_pdf(file_path)
    elif file_type == "xml":
        loader = XMLLoader()
        xml_chunks, extracted_xml_metrics = loader.load_xml(file_path)
        for idx, chunk in enumerate(xml_chunks):
            extracted_pages.append({
                "page_num": idx + 1,
                "text": chunk["content"]
            })
            
    return {
        "file_path": file_path,
        "file_name": os.path.basename(file_path),
        "company": company,
        "year": year,
        "file_type": file_type,
        "file_hash": file_hash,
        "pages": extracted_pages,
        "tables": extracted_tables,
        "xml_metrics": extracted_xml_metrics
    }

class DocumentManager:
    def __init__(self):
        self.index_path = settings.DOC_INDEX_PATH
        self.load_index()
        
    def load_index(self):
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, "r") as f:
                    self.index = json.load(f)
            except Exception:
                self.index = {}
        else:
            self.index = {}

    def save_index(self):
        with open(self.index_path, "w") as f:
            json.dump(self.index, f, indent=2)

    def scan_raw_directory(self) -> List[Tuple[str, str, str, str]]:
        """
        Scans data/raw_reports/ for Company_Name/Year/files
        Returns a list of tuples: (file_path, company, year, file_type)
        """
        raw_files = []
        raw_dir = settings.RAW_DIR
        
        if not raw_dir.exists():
            return raw_files
            
        for company_dir in raw_dir.iterdir():
            if company_dir.is_dir():
                company_name = company_dir.name
                for year_dir in company_dir.iterdir():
                    if year_dir.is_dir():
                        year = year_dir.name
                        for report_file in year_dir.iterdir():
                            if report_file.is_file():
                                ext = report_file.suffix.lower()[1:]
                                if ext in ["pdf", "xml"]:
                                    raw_files.append((
                                        str(report_file),
                                        company_name,
                                        year,
                                        ext
                                    ))
        return raw_files

    def ingest_new_reports(self, target_files: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Scans reports, determines which ones are new or changed,
        and parses them in parallel. Then computes embeddings and populates DBs.
        """
        raw_files = self.scan_raw_directory()
        if target_files is not None:
            target_abs = {os.path.abspath(f) for f in target_files}
            raw_files = [f for f in raw_files if os.path.abspath(f[0]) in target_abs]
        
        files_to_process = []
        
        # Check hashes
        for file_path, company, year, file_type in raw_files:
            file_name = os.path.basename(file_path)
            
            # Calculate quick hash to see if we should enqueue
            hasher = hashlib.sha256()
            with open(file_path, "rb") as f:
                buf = f.read(65536)
                while len(buf) > 0:
                    hasher.update(buf)
                    buf = f.read(65536)
            file_hash = hasher.hexdigest()
            
            existing = self.index.get(file_path)
            if not existing or existing.get("file_hash") != file_hash:
                files_to_process.append((file_path, company, year, file_type))
                
        if not files_to_process:
            return {"status": "success", "message": "No new or modified documents found.", "processed": 0}
            
        # Parallel parsing
        parsed_results = []
        max_workers = min(os.cpu_count() or 1, len(files_to_process))
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            parsed_results = list(executor.map(_parse_single_file, files_to_process))
            
        # Initialize databases (Singletons / cached clients in main process)
        from src.retrieval.company_router import CompanyRouter
        company_router = CompanyRouter()
        chroma_store = ChromaStore()
        metrics_store = MetricsStore()
        embedding_manager = EmbeddingManager()
        chunker = Chunker()
        extractor = MetricExtractor()
        query_cache = QueryCache()
        
        processed_count = 0
        for res in parsed_results:
            file_path = res["file_path"]
            company = res["company"]
            
            # Resolve canonical company name
            resolved_comps, _ = company_router.resolve_companies_and_years(company)
            if resolved_comps:
                company = resolved_comps[0]
                
            year = res["year"]
            file_hash = res["file_hash"]
            file_type = res["file_type"]
            file_name = res["file_name"]
            
            # Clear old records to avoid duplication if file changed
            chroma_store.delete_company_year(company, year)
            metrics_store.clear_company_metrics(company, year)
            query_cache.clear_cache(company, year)
            
            # Generate Chunks
            all_chunks = []
            for page in res["pages"]:
                page_chunks = chunker.chunk_page(
                    page_text=page["text"],
                    page_num=page["page_num"],
                    company=company,
                    year=year,
                    source_file=file_name
                )
                all_chunks.extend(page_chunks)
                
            # Extract Metrics from text paragraphs
            metrics_to_save = []
            for chunk in all_chunks:
                text_metrics = extractor.extract_from_text(chunk["content"])
                for m in text_metrics:
                    m["company"] = company
                    m["year"] = year
                    m["source_file"] = file_name
                    m["page"] = chunk["page"]
                    metrics_to_save.append(m)
                    
            # Extract Metrics from tables (for PDFs)
            for page_num, table in res["tables"]:
                table_metrics = extractor.extract_from_table(table, year)
                for m in table_metrics:
                    m["company"] = company
                    m["year"] = year
                    m["source_file"] = file_name
                    m["page"] = str(page_num)
                    metrics_to_save.append(m)
                    
            # Add XML direct metrics if parsed
            for m in res["xml_metrics"]:
                m["company"] = company
                m["year"] = year
                m["source_file"] = file_name
                metrics_to_save.append(m)
                
            # Deduplicate metrics before saving to SQLite
            dedup_metrics = {}
            for m in metrics_to_save:
                key = (m["company"], m["year"], m["metric_key"], m["source_file"])
                # Prefer table/xml parsed values or higher fidelity
                dedup_metrics[key] = m
                
            metrics_store.save_metrics_batch(list(dedup_metrics.values()))
            
            # Embed chunks in batch and insert to ChromaDB
            if all_chunks:
                chunk_texts = [c["content"] for c in all_chunks]
                embeddings = embedding_manager.get_embeddings(chunk_texts, batch_size=64)
                
                ids = [f"{company}_{year}_{file_name}_p{c['page']}_{idx}" for idx, c in enumerate(all_chunks)]
                metadatas = [{
                    "company": c["company"],
                    "year": str(c["year"]),
                    "section_type": c["section_type"],
                    "source_file": c["source_file"],
                    "page": str(c["page"])
                } for c in all_chunks]
                
                chroma_store.add_chunks(
                    ids=ids,
                    documents=chunk_texts,
                    embeddings=embeddings,
                    metadatas=metadatas
                )
                
            # Update index
            self.index[file_path] = {
                "file_name": file_name,
                "file_path": file_path,
                "company": company,
                "year": year,
                "file_type": file_type,
                "file_hash": file_hash,
                "processed_date": datetime.now().isoformat(),
                "status": "success",
                "chunks": len(all_chunks)
            }
            processed_count += 1
            
        self.save_index()
        return {"status": "success", "message": f"Processed {processed_count} files.", "processed": processed_count}
