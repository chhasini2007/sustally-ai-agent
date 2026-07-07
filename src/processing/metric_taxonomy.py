# Canonical taxonomy dictionary mapping keys to their metadata and common query aliases/synonyms

METRIC_TAXONOMY = {
    "scope1_emissions_tco2e": {
        "label": "Scope 1 Emissions",
        "unit": "tCO2e",
        "synonyms": [
            "scope 1", "scope 1 emissions", "direct emissions", "direct ghg emissions", 
            "scope 1 greenhouse gas emissions", "scope 1 ghg emissions"
        ],
        "patterns": [
            r"scope\s*1\s*(?:emissions|ghg|greenhouse\s*gas)?",
            r"direct\s*(?:ghg|emissions|greenhouse\s*gas\s*emissions)"
        ]
    },
    "scope2_emissions_tco2e": {
        "label": "Scope 2 Emissions",
        "unit": "tCO2e",
        "synonyms": [
            "scope 2", "scope 2 emissions", "indirect emissions", "indirect ghg emissions", 
            "location-based scope 2", "market-based scope 2", "scope 2 greenhouse gas emissions",
            "scope 2 ghg emissions"
        ],
        "patterns": [
            r"scope\s*2\s*(?:emissions|ghg|greenhouse\s*gas)?",
            r"indirect\s*(?:ghg|emissions|greenhouse\s*gas\s*emissions)"
        ]
    },
    "scope3_emissions_tco2e": {
        "label": "Scope 3 Emissions",
        "unit": "tCO2e",
        "synonyms": [
            "scope 3", "scope 3 emissions", "value chain emissions", "other indirect emissions",
            "scope 3 greenhouse gas emissions", "scope 3 ghg emissions"
        ],
        "patterns": [
            r"scope\s*3\s*(?:emissions|ghg|greenhouse\s*gas)?"
        ]
    },
    "water_consumption_kl": {
        "label": "Water Consumption",
        "unit": "kl",
        "synonyms": [
            "water consumption", "water consumed", "water usage", "total water consumed", 
            "water withdrawal", "total water consumption"
        ],
        "patterns": [
            r"water\s*consumption",
            r"water\s*consumed",
            r"water\s*usage",
            r"total\s*water\s*consumed"
        ]
    },
    "renewable_energy_pct": {
        "label": "Renewable Energy Share",
        "unit": "%",
        "synonyms": [
            "renewable energy share", "renewable energy percentage", "renewable energy",
            "renewable source", "renewable electricity percentage", "renewable power share",
            "renewable energy consumption percentage"
        ],
        "patterns": [
            r"renewable\s*energy\s*(?:share|percentage|pct|electricity|power)?",
            r"share\s*of\s*renewable\s*energy"
        ]
    },
    "women_workforce_pct": {
        "label": "Women in Workforce",
        "unit": "%",
        "synonyms": [
            "women in workforce", "percentage of women", "female employees percentage", 
            "female representation", "women representation", "women workforce percentage", 
            "gender diversity", "female employees", "women employees"
        ],
        "patterns": [
            r"women\s*(?:in|workforce|employees|representation|pct|percentage)?",
            r"female\s*(?:employees|representation|pct|percentage|workforce)?"
        ]
    },
    "waste_generation_tonnes": {
        "label": "Total Waste Generated",
        "unit": "tonnes",
        "synonyms": [
            "waste generation", "total waste generated", "waste generated", 
            "hazardous waste generated", "non-hazardous waste generated"
        ],
        "patterns": [
            r"waste\s*generated",
            r"total\s*waste\s*generated",
            r"waste\s*generation"
        ]
    }
}

# Fast lookup dictionary mapping aliases to canonical key
ALIASED_METRICS = {}
for canonical_key, info in METRIC_TAXONOMY.items():
    for synonym in info["synonyms"]:
        ALIASED_METRICS[synonym.lower()] = canonical_key
