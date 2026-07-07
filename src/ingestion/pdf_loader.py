import pdfplumber
from typing import List, Dict, Any, Tuple

class PDFLoader:
    def load_pdf(self, file_path: str) -> Tuple[List[Dict[str, Any]], List[List[List[str]]]]:
        """
        Loads PDF, returns:
        1. List of page dicts: [{"page_num": int, "text": str}]
        2. List of tables: [table1, table2, ...] where table is List[List[str]]
        """
        pages_data = []
        all_tables = []
        
        with pdfplumber.open(file_path) as pdf:
            for idx, page in enumerate(pdf.pages):
                page_num = idx + 1
                text = page.extract_text() or ""
                pages_data.append({
                    "page_num": page_num,
                    "text": text
                })
                
                # Extract tables
                try:
                    tables = page.extract_tables()
                    for table in tables:
                        if table:
                            # Attach page context to the table by adding page number as a metadata/info field if needed,
                            # or just keep it in all_tables list. Let's record the page number with the table.
                            # We can represent a table as a tuple: (page_num, table_data)
                            all_tables.append((page_num, table))
                except Exception:
                    pass # Ignore table parsing errors for robustness
                    
        return pages_data, all_tables
