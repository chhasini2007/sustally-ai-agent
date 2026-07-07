from typing import List, Dict, Any
from src.processing.normalizer import Normalizer

class Chunker:
    def __init__(self):
        self.normalizer = Normalizer()

    def chunk_page(
        self,
        page_text: str,
        page_num: int,
        company: str,
        year: str,
        source_file: str
    ) -> List[Dict[str, Any]]:
        cleaned_text = self.normalizer.clean_text(page_text)
        if not cleaned_text or len(cleaned_text) < 50:
            return []

        section_type = self.normalizer.classify_section(cleaned_text)
        
        # In a standard report, a single page is about 300-800 words, which is a perfect chunk size (1000-3000 chars).
        # We can treat each page as one semantic chunk. If it is exceptionally large (e.g. > 4000 characters), we split by paragraphs.
        chunks = []
        if len(cleaned_text) > 4000:
            paragraphs = cleaned_text.split("\n\n")
            current_chunk = []
            current_len = 0
            chunk_num = 1
            for para in paragraphs:
                if not para.strip():
                    continue
                current_chunk.append(para)
                current_len += len(para)
                if current_len >= 2500:
                    chunk_content = "\n\n".join(current_chunk)
                    chunks.append({
                        "company": company,
                        "year": str(year),
                        "section": f"Page {page_num} - Part {chunk_num}",
                        "section_type": self.normalizer.classify_section(chunk_content),
                        "content": chunk_content,
                        "source_file": source_file,
                        "page": str(page_num)
                    })
                    current_chunk = []
                    current_len = 0
                    chunk_num += 1
            if current_chunk:
                chunk_content = "\n\n".join(current_chunk)
                chunks.append({
                    "company": company,
                    "year": str(year),
                    "section": f"Page {page_num} - Part {chunk_num}",
                    "section_type": self.normalizer.classify_section(chunk_content),
                    "content": chunk_content,
                    "source_file": source_file,
                    "page": str(page_num)
                })
        else:
            chunks.append({
                "company": company,
                "year": str(year),
                "section": f"Page {page_num}",
                "section_type": section_type,
                "content": cleaned_text,
                "source_file": source_file,
                "page": str(page_num)
            })
            
        return chunks
