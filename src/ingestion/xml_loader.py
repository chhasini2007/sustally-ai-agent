import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple
from src.processing.metric_taxonomy import METRIC_TAXONOMY

class XMLLoader:
    def load_xml(self, file_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Loads XML, extracts text content and direct structured metrics.
        Returns:
        - List of chunks: [{"section": str, "content": str, "page": str}]
        - List of extracted metrics: [{"metric_key": str, "metric_label": str, "value": float, "unit": str, "page": str}]
        """
        chunks = []
        metrics = []
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Simple recursive helper to extract all tag content
            all_text_elements = []
            
            def recurse(node, path=""):
                current_path = f"{path}/{node.tag}" if path else node.tag
                tag_name = node.tag.lower()
                
                # Check if tag matches any taxonomy metric directly
                matched_key = None
                for key, info in METRIC_TAXONOMY.items():
                    # Check if tag is similar to key or synonym
                    if tag_name == key.lower() or any(syn in tag_name for syn in info["synonyms"]):
                        matched_key = key
                        break
                
                # If matched, try to extract numerical value
                if matched_key and node.text:
                    val_str = node.text.strip().replace(",", "")
                    # Extract numeric part
                    num_match = re.search(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?", val_str)
                    if num_match:
                        try:
                            val = float(num_match.group(0))
                            unit = node.attrib.get("unit", METRIC_TAXONOMY[matched_key]["unit"])
                            metrics.append({
                                "metric_key": matched_key,
                                "metric_label": f"XML Tag: {current_path}",
                                "value": val,
                                "unit": unit,
                                "page": "XML"
                            })
                        except ValueError:
                            pass
                
                if node.text and node.text.strip():
                    all_text_elements.append(f"{node.tag}: {node.text.strip()}")
                    
                for child in node:
                    recurse(child, current_path)
                    
            import re
            recurse(root)
            
            # Group all XML text into a single cohesive narrative chunk
            full_text = "\n".join(all_text_elements)
            chunks.append({
                "section": "XML Content",
                "content": full_text,
                "page": "XML"
            })
            
        except Exception as e:
            # Add basic dummy chunk for structural fallback
            chunks.append({
                "section": "XML Error",
                "content": f"Failed to parse XML file: {str(e)}",
                "page": "XML"
            })
            
        return chunks, metrics
