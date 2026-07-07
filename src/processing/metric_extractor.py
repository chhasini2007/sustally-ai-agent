import re
from typing import List, Dict, Any, Tuple, Optional
from src.processing.metric_taxonomy import METRIC_TAXONOMY

class MetricExtractor:
    def __init__(self):
        # Precompile regexes
        self.number_pattern = re.compile(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?")

    def extract_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Scans text paragraphs for metric-like lines.
        Example: "Scope 1 emissions: 12,450 tCO2e" or "Renewable energy usage: 45.2%"
        """
        extracted = []
        lines = text.split("\n")
        
        for line in lines:
            if not line.strip():
                continue
                
            for key, info in METRIC_TAXONOMY.items():
                for pattern in info["patterns"]:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        # Find numbers near or after the pattern
                        remaining_text = line[match.end():]
                        num_match = self.number_pattern.search(remaining_text)
                        if num_match:
                            num_str = num_match.group(0).replace(",", "")
                            try:
                                val = float(num_str)
                                # Check if unit is in the text
                                unit = info["unit"]
                                # Check if actual unit matches (e.g. tCO2e or % or kl)
                                extracted.append({
                                    "metric_key": key,
                                    "metric_label": line.strip()[:100], # Keep a snippet
                                    "value": val,
                                    "unit": unit
                                })
                                break # Stop checking other patterns for this key in this line
                            except ValueError:
                                continue
        return extracted

    def extract_from_table(self, table: List[List[str]], report_year: str) -> List[Dict[str, Any]]:
        """
        Given a table parsed by pdfplumber/camelot (list of rows where each row is a list of cell strings),
        extract metrics matching the taxonomy.
        """
        extracted = []
        if not table or len(table) < 2:
            return extracted

        # Try to find year columns
        header = [str(cell or "").strip().lower() for cell in table[0]]
        year_idx = -1
        
        # Look for matching year in headers
        year_short = report_year[-2:] if len(report_year) >= 2 else report_year
        for idx, col in enumerate(header):
            if report_year in col or f"fy{year_short}" in col or f"fy {year_short}" in col or f"fy20{year_short}" in col:
                year_idx = idx
                break
                
        # If no specific year column found, default to finding the first numeric column after the row label
        for row in table[1:]:
            if not row or not row[0]:
                continue
            row_label = str(row[0]).strip().lower()
            
            for key, info in METRIC_TAXONOMY.items():
                match_found = False
                for pattern in info["patterns"]:
                    if re.search(pattern, row_label, re.IGNORECASE):
                        match_found = True
                        break
                
                if match_found:
                    # Select target column
                    val_str = None
                    if year_idx != -1 and year_idx < len(row):
                        val_str = row[year_idx]
                    else:
                        # Fall back to finding the first non-empty cell that contains a number
                        for cell in row[1:]:
                            if cell and self.number_pattern.search(str(cell)):
                                val_str = cell
                                break
                    
                    if val_str:
                        num_match = self.number_pattern.search(str(val_str))
                        if num_match:
                            val_clean = num_match.group(0).replace(",", "")
                            try:
                                val = float(val_clean)
                                extracted.append({
                                    "metric_key": key,
                                    "metric_label": str(row[0]).strip(),
                                    "value": val,
                                    "unit": info["unit"]
                                })
                            except ValueError:
                                continue
        return extracted
