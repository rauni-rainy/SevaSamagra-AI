import re

BIO_RISK_LEXICON = {
    "stagnant_water": [
        "stagnant water", "ruka hua paani", "naali band", 
        "blocked drain", "standing water", "paani ruka"
    ],
    "waterborne_risk": [
        "diarrhoea", "diarrhea", "stomach pain", "pet dard", 
        "loose motions", "vomiting", "ulti", "cholera"
    ],
    "vector_risk": [
        "mosquitoes", "machhar", "rats", "chuhe", 
        "dead animals", "foul smell", "badbu", "machar"
    ],
    "sanitation_failure": [
        "open defecation", "no toilet", "sewage overflow", 
        "naali uf rahi", "ganda paani", "dirty water"
    ],
    "water_supply": [
        "no water", "paani nahi", "pump broken", 
        "handpump kharab", "water pump", "no drinking water"
    ]
}

def extract_need_info(text: str) -> dict:
    """
    Extracts structured need, location, urgency, and bio-markers from a given text.
    
    Args:
        text (str): The plain text transcript to analyze.
        
    Returns:
        dict: A dictionary containing 'extracted_need', 'extracted_location',
              'urgency_level', 'bio_markers_detected', and 'language_detected'.
    """
    text_lower = text.lower()
    
    # Simple bio marker extraction
    bio_markers_detected = set()
    for category, keywords in BIO_RISK_LEXICON.items():
        for keyword in keywords:
            if keyword in text_lower:
                bio_markers_detected.add(category)
                break
                
    # Urgency extraction
    high_urgency_keywords = ["emergency", "bahut urgent", "4 din se", "children sick", "no water"]
    urgency_level = "medium"
    for keyword in high_urgency_keywords:
        if keyword in text_lower:
            urgency_level = "critical"
            break
            
    # Language detection (heuristic based on common hindi words in latin script)
    hindi_keywords = ["paani", "nahi", "kharab", "dard", "ruka", "hua", "band", "chuhe", "machhar", "machar"]
    hindi_hits = sum(1 for kw in hindi_keywords if kw in text_lower)
    
    english_keywords = ["water", "pain", "broken", "drain", "stagnant"]
    english_hits = sum(1 for kw in english_keywords if kw in text_lower)
    
    if hindi_hits > 0 and english_hits > 0:
        language_detected = "mixed"
    elif hindi_hits > 0:
        language_detected = "hindi"
    else:
        language_detected = "english"
        
    # Extracted need (simplistic - takes first sentence or full text if short)
    extracted_need = text.split(". ")[0] if ". " in text else text
    
    # Location extraction (dummy simple heuristic for demo, looking for English & Hindi prepositions)
    extracted_location = "Unknown"
    
    # 1. English grammar format (Preposition BEFORE Location)
    location_match = re.search(r'\b(in|at|near|from)\s+([A-Za-z0-9\s]{3,20})', text_lower)
    if location_match:
        extracted_location = location_match.group(2).strip().title()
    else:
        # 2. Hindi grammar format (Preposition AFTER Location)
        hindi_loc_match = re.search(r'\b([A-Za-z0-9\s]{3,20})\s+(pe|mein|me|par|se)\b', text_lower)
        if hindi_loc_match:
            loc_words = hindi_loc_match.group(1).split()
            # Grab just the last 2 words before the preposition to avoid matching the whole sentence
            words_to_take = loc_words[-2:] if len(loc_words) >= 2 else loc_words
            loc_string = " ".join([w for w in words_to_take if w.lower() not in ["yha", "yahan", "hai", "ka", "ki"]])
            if loc_string.strip():
                extracted_location = loc_string.strip().title()

    return {
        "extracted_need": extracted_need,
        "extracted_location": extracted_location,
        "urgency_level": urgency_level,
        "bio_markers_detected": list(bio_markers_detected),
        "language_detected": language_detected
    }
