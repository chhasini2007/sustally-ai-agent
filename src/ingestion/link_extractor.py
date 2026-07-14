import os
import re
try:
    import fitz  # PyMuPDF
    _ = fitz.Rect
    HAS_FITZ = True
except (ImportError, AttributeError, Exception):
    HAS_FITZ = False
import requests
import hashlib
from typing import List, Dict, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
from urllib3.util import Retry
from requests.adapters import HTTPAdapter
from pathlib import Path

from config import settings
from src.retrieval.company_router import CompanyRouter
from src.ingestion.document_manager import DocumentManager
from src.database.metrics_store import MetricsStore

class LinkExtractorUtility:
    def __init__(self):
        self.company_router = CompanyRouter()
        self.document_manager = DocumentManager()
        self.url_regex = re.compile(
            r'https?://(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?::\d+)?(?:/[^\s"\']*)?'
        )
        self.year_regex = re.compile(r"(?<!\d)(20\d{2}|19\d{2})(?!\d)")

    def extract_links_from_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Scans PDF, extracts hyperlink annotations and text URLs.
        Returns:
            List[Dict[str, Any]]: [{"url": str, "page": int, "context": str}]
        """
        extracted = []
        seen_urls = set()

        if HAS_FITZ:
            doc = fitz.open(pdf_path)
            for page_num, page in enumerate(doc):
                page_idx = page_num + 1
                page_text = page.get_text()
                
                # 1. Extract link annotations
                for link in page.get_links():
                    uri = link.get("uri")
                    if uri and uri not in seen_urls:
                        seen_urls.add(uri)
                        extracted.append({
                            "url": uri,
                            "page": page_idx,
                            "context": page_text
                        })
                
                # 2. Extract plain text URLs using regex
                matches = self.url_regex.findall(page_text)
                for uri in matches:
                    if uri not in seen_urls:
                        seen_urls.add(uri)
                        extracted.append({
                            "url": uri,
                            "page": page_idx,
                            "context": page_text
                        })
        else:
            # Fallback using pypdf
            from pypdf import PdfReader
            reader = PdfReader(pdf_path)
            for page_num, page in enumerate(reader.pages):
                page_idx = page_num + 1
                page_text = page.extract_text() or ""
                
                # 1. Extract link annotations
                if "/Annots" in page:
                    for annot in page["/Annots"]:
                        obj = annot.get_object()
                        if obj and obj.get("/Subtype") == "/Link":
                            if "/A" in obj and "/URI" in obj["/A"]:
                                uri = obj["/A"]["/URI"]
                                if uri and uri not in seen_urls:
                                    seen_urls.add(uri)
                                    extracted.append({
                                        "url": uri,
                                        "page": page_idx,
                                        "context": page_text
                                    })
                
                # 2. Extract plain text URLs using regex
                matches = self.url_regex.findall(page_text)
                for uri in matches:
                    if uri not in seen_urls:
                        seen_urls.add(uri)
                        extracted.append({
                            "url": uri,
                            "page": page_idx,
                            "context": page_text
                        })

        return extracted

    def is_report_link(self, url: str, session: requests.Session) -> Tuple[bool, str, str]:
        """
        Verifies if the URL links to an XML or PDF report resource.
        Returns:
            (is_report: bool, file_type: str, reason: str)
        """
        url_lower = url.lower()
        
        # Pass 1: Cheap path/query check
        if "xml" in url_lower:
            return True, "xml", "Cheap check: URL contains 'xml'"
        if "pdf" in url_lower:
            return True, "pdf", "Cheap check: URL contains 'pdf'"
            
        # Pass 2: HEAD request verification for ambiguous URLs
        try:
            resp = session.head(url, timeout=5, allow_redirects=True)
            content_type = resp.headers.get("Content-Type", "").lower()
            
            if "application/pdf" in content_type:
                return True, "pdf", f"Verified HEAD: Content-Type is PDF ({content_type})"
            if "xml" in content_type:
                return True, "xml", f"Verified HEAD: Content-Type contains xml ({content_type})"
                
            # As a final fallback, try GET headers (sometimes HEAD is not supported)
            if resp.status_code in [404, 405]:
                resp_get = session.get(url, timeout=5, allow_redirects=True, stream=True)
                content_type = resp_get.headers.get("Content-Type", "").lower()
                resp_get.close()
                if "application/pdf" in content_type:
                    return True, "pdf", f"Verified GET: Content-Type is PDF ({content_type})"
                if "xml" in content_type:
                    return True, "xml", f"Verified GET: Content-Type contains xml ({content_type})"
                    
            return False, "unresolved", f"Skipped: Content-Type ({content_type}) does not contain xml/pdf"
        except Exception as e:
            return False, "unresolved", f"Error verifying HEAD: {str(e)}"

    def is_xml_link(self, url: str, session: requests.Session) -> Tuple[bool, str]:
        """
        Verifies if the URL links to an XML format resource.
        Returns:
            (is_xml: bool, reason: str)
        """
        is_report, file_type, reason = self.is_report_link(url, session)
        return (is_report and file_type == "xml"), reason

    def resolve_company_year(self, context_text: str, url: str) -> Tuple[str, str]:
        """
        Tries to resolve the company and year from the context surrounding the link.
        If unresolved, returns ('_unsorted', 'unknown')
        """
        # Resolve company
        resolved_companies, years = self.company_router.resolve_companies_and_years(context_text)
        
        # If not resolved in text, try matching URL path
        if not resolved_companies:
            cleaned_url = url.replace("_", " ").replace("-", " ").replace("/", " ").replace(".", " ")
            resolved_companies, _ = self.company_router.resolve_companies_and_years(cleaned_url)
            
        if not years:
            years = self.year_regex.findall(url)

        company = resolved_companies[0] if resolved_companies else "_unsorted"
        year = years[0] if years else "unknown"
        
        return company, year

    def download_single_link(self, item: Dict[str, Any], session: requests.Session) -> Dict[str, Any]:
        url = item["url"]
        context = item["context"]
        page = item["page"]
        
        is_report, file_type, reason = self.is_report_link(url, session)
        if not is_report:
            return {"url": url, "status": "unresolved", "reason": reason}
            
        # Resolve destination metadata
        company, year = self.resolve_company_year(context, url)
        
        try:
            # Download file
            resp = session.get(url, timeout=15, allow_redirects=True)
            resp.raise_for_status()
            content = resp.content
            
            # Compute hash
            content_hash = hashlib.sha256(content).hexdigest()
            
            # Check if already indexed
            is_indexed = False
            for path, val in self.document_manager.index.items():
                if val.get("file_hash") == content_hash:
                    is_indexed = True
                    break
                    
            if is_indexed:
                return {"url": url, "status": "skipped_indexed", "company": company, "year": year, "file_type": file_type}
                
            # Create directories
            target_dir = Path(settings.RAW_DIR) / company / year
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Detect unique file name
            file_name = f"report.{file_type}"
            target_path = target_dir / file_name
            suffix = 1
            while target_path.exists():
                file_name = f"report_{suffix}.{file_type}"
                target_path = target_dir / file_name
                suffix += 1
                
            with open(target_path, "wb") as f:
                f.write(content)
                
            return {
                "url": url,
                "status": "downloaded",
                "company": company,
                "year": year,
                "path": str(target_path),
                "file_type": file_type
            }
        except Exception as e:
            return {"url": url, "status": "error", "reason": f"Download failed: {str(e)}"}

    def run_extractor(self, pdf_path: str) -> Dict[str, Any]:
        """
        Runs link extraction, filtering, downloading, and feeds ingestion.
        """
        print(f"Extracting links from master report: {pdf_path}")
        raw_links = self.extract_links_from_pdf(pdf_path)
        
        # Setup session with retry adapter
        session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        session.mount("http://", HTTPAdapter(max_retries=retries))
        session.mount("https://", HTTPAdapter(max_retries=retries))
        
        results = []
        # Multi-threaded download
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(self.download_single_link, item, session) for item in raw_links]
            for f in futures:
                results.append(f.result())
                
        # Count outcomes
        summary = {
            "found": len(raw_links),
            "xml_matched": 0,
            "pdf_skipped": 0,
            "unresolved": 0,
            "downloaded": 0,
            "skipped_indexed": 0,
            "unsorted": 0
        }
        
        downloaded_paths = []
        for res in results:
            status = res["status"]
            if status == "unresolved":
                summary["unresolved"] += 1
            elif status == "skipped_indexed":
                summary["xml_matched"] += 1
                summary["skipped_indexed"] += 1
            elif status == "downloaded":
                summary["xml_matched"] += 1
                summary["downloaded"] += 1
                downloaded_paths.append(res["path"])
                if res["company"] == "_unsorted":
                    summary["unsorted"] += 1
            elif status == "error":
                summary["unresolved"] += 1
                
        # If new files were downloaded, trigger DocumentManager ingestion
        if downloaded_paths:
            print(f"Informing DocumentManager to ingest {len(downloaded_paths)} newly downloaded reports...")
            self.document_manager.load_index() # reload index
            path_to_url = {res["path"]: res["url"] for res in results if res["status"] == "downloaded"}
            self.document_manager.ingest_new_reports(target_files=downloaded_paths, source_urls=path_to_url)
            
        return summary
