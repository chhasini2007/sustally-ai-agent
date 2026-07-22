"""
Canonical ESG Metric Taxonomy & Normalization Registry
Supports full canonical resolution across Scope 1-3 emissions, water, energy, waste,
diversity, targets, and carbon intensity.
"""
from typing import Dict, Any, Optional, List
import re

METRIC_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "scope1_emissions": {
        "label": "Scope 1 Emissions",
        "unit": "tCO2e",
        "category": "Environmental",
        "synonyms": [
            "scope 1", "scope 1 emissions", "direct emissions", "direct ghg emissions", 
            "scope 1 greenhouse gas emissions", "scope 1 ghg emissions",
            "scope i", "ghg scope 1", "direct ghg", "carbon scope 1", "totalscope1emissions",
            "scope1_emissions_tco2e"
        ],
        "patterns": [
            r"scope\s*1\s*(?:emissions|ghg|greenhouse\s*gas)?",
            r"direct\s*(?:ghg|emissions|greenhouse\s*gas\s*emissions)",
            r"totalscope1emissions"
        ]
    },
    "scope2_emissions": {
        "label": "Scope 2 Emissions",
        "unit": "tCO2e",
        "category": "Environmental",
        "synonyms": [
            "scope 2", "scope 2 emissions", "indirect emissions", "indirect ghg emissions", 
            "location-based scope 2", "market-based scope 2", "scope 2 greenhouse gas emissions",
            "scope 2 ghg emissions", "scope ii", "ghg scope 2", "totalscope2emissions",
            "scope2_emissions_tco2e"
        ],
        "patterns": [
            r"scope\s*2\s*(?:emissions|ghg|greenhouse\s*gas)?",
            r"indirect\s*(?:ghg|emissions|greenhouse\s*gas\s*emissions)",
            r"totalscope2emissions"
        ]
    },
    "scope3_emissions": {
        "label": "Scope 3 Emissions",
        "unit": "tCO2e",
        "category": "Environmental",
        "synonyms": [
            "scope 3", "scope 3 emissions", "value chain emissions", "other indirect emissions",
            "scope 3 greenhouse gas emissions", "scope 3 ghg emissions", "scope iii", "ghg scope 3",
            "totalscope3emissions", "scope3_emissions_tco2e"
        ],
        "patterns": [
            r"scope\s*3\s*(?:emissions|ghg|greenhouse\s*gas)?",
            r"totalscope3emissions"
        ]
    },
    "water_consumption_kl": {
        "label": "Water Consumption",
        "unit": "kl",
        "category": "Environmental",
        "synonyms": [
            "water consumption", "water consumed", "water usage", "total water consumed", 
            "water withdrawal", "total water consumption", "fresh water withdrawal", "water intake", "total water used"
        ],
        "patterns": [
            r"water\s*consumption",
            r"water\s*consumed",
            r"water\s*usage",
            r"total\s*water\s*consumed"
        ]
    },
    "water_recycled_kl": {
        "label": "Water Recycled",
        "unit": "kl",
        "category": "Environmental",
        "synonyms": [
            "water recycled", "water reused", "recycled water", "total water recycled",
            "reused water", "percentage of water recycled"
        ],
        "patterns": [
            r"water\s*recycled",
            r"water\s*reused",
            r"recycled\s*water"
        ]
    },
    "energy_consumption_gj": {
        "label": "Energy Consumption",
        "unit": "GJ",
        "category": "Environmental",
        "synonyms": [
            "energy consumption", "total energy consumption", "energy usage",
            "energy consumed", "total energy used", "fuel consumption"
        ],
        "patterns": [
            r"energy\s*consumption",
            r"energy\s*consumed",
            r"total\s*energy\s*usage"
        ]
    },
    "renewable_energy_pct": {
        "label": "Renewable Energy Share",
        "unit": "%",
        "category": "Environmental",
        "synonyms": [
            "renewable energy share", "renewable energy percentage", "renewable energy",
            "renewable source", "renewable electricity percentage", "renewable power share",
            "renewable energy consumption percentage", "green energy", "clean energy"
        ],
        "patterns": [
            r"renewable\s*energy\s*(?:share|percentage|pct|electricity|power)?",
            r"share\s*of\s*renewable\s*energy"
        ]
    },
    "waste_generation_tonnes": {
        "label": "Total Waste Generated",
        "unit": "tonnes",
        "category": "Environmental",
        "synonyms": [
            "waste generation", "total waste generated", "waste generated", "total waste"
        ],
        "patterns": [
            r"waste\s*generated",
            r"total\s*waste\s*generated",
            r"waste\s*generation"
        ]
    },
    "hazardous_waste_tonnes": {
        "label": "Hazardous Waste Generated",
        "unit": "tonnes",
        "category": "Environmental",
        "synonyms": [
            "hazardous waste", "hazardous waste generated", "toxic waste", "hazardous waste count"
        ],
        "patterns": [
            r"hazardous\s*waste\s*(?:generated)?"
        ]
    },
    "female_employee_headcount_share_pct": {
        "label": "Female Employee Headcount Share",
        "unit": "%",
        "category": "Social",
        "synonyms": [
            "female employee headcount share", "percentage of female employees", "female employee share", 
            "how many female employees", "percentage of women employees", "percentage of women", 
            "female representation", "women representation", "women workforce percentage", 
            "gender diversity", "female employees", "women employees", "women in workforce",
            "female workforce", "women workforce", "women ratio"
        ],
        "patterns": [
            r"female\s*employee\s*(?:share|percentage|pct)",
            r"percentage\s*of\s*female\s*employees",
            r"women\s*workforce\s*(?:share|percentage|pct)",
            r"female\s*representation",
            r"female\s*employees",
            r"women\s*employees"
        ]
    },
    "diversity_pct": {
        "label": "Diversity Index & Representation",
        "unit": "%",
        "category": "Social",
        "synonyms": [
            "diversity", "diversity ratio", "workforce diversity", "employee diversity",
            "inclusion index", "board diversity"
        ],
        "patterns": [
            r"\bdiversity\b",
            r"diversity\s*ratio",
            r"workforce\s*diversity"
        ]
    },
    "net_zero_target_year": {
        "label": "Net Zero Target Year",
        "unit": "year",
        "category": "Environmental",
        "synonyms": [
            "net zero target", "net zero target year", "decarbonization target",
            "net-zero goal", "carbon neutral target year"
        ],
        "patterns": [
            r"net\s*zero\s*target",
            r"carbon\s*neutral\s*target"
        ]
    },
    "carbon_intensity": {
        "label": "Carbon Intensity",
        "unit": "tCO2e per revenue",
        "category": "Environmental",
        "synonyms": [
            "carbon intensity", "ghg intensity", "emissions intensity", "carbon footprint intensity"
        ],
        "patterns": [
            r"carbon\s*intensity",
            r"emissions\s*intensity"
        ]
    }
}

# Alias mapping with backward-compatibility for scope1_emissions_tco2e -> scope1_emissions
ALIASED_METRICS: Dict[str, str] = {}
for canonical_key, info in METRIC_TAXONOMY.items():
    for synonym in info["synonyms"]:
        ALIASED_METRICS[synonym.lower()] = canonical_key

# Aliases for legacy metric keys
ALIASED_METRICS["scope1_emissions_tco2e"] = "scope1_emissions"
ALIASED_METRICS["scope2_emissions_tco2e"] = "scope2_emissions"
ALIASED_METRICS["scope3_emissions_tco2e"] = "scope3_emissions"


def resolve_canonical_metric(text: str) -> Optional[str]:
    text_lower = text.lower().strip()
    if text_lower in ALIASED_METRICS:
        return ALIASED_METRICS[text_lower]

    sorted_synonyms = sorted(ALIASED_METRICS.keys(), key=len, reverse=True)
    for synonym in sorted_synonyms:
        if synonym in text_lower:
            return ALIASED_METRICS[synonym]

    for canonical_key, info in METRIC_TAXONOMY.items():
        for pat in info.get("patterns", []):
            if re.search(pat, text_lower):
                return canonical_key

    return None
