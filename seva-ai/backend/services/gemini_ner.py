"""
gemini_ner.py — Gemini-powered Named Entity Recognition for field reports.

Uses the new google-genai SDK (google.genai). Single API call per report.
Extracts: location name, geocodeable query, urgency, bio-markers, need summary.
Forward-geocodes via Nominatim OSM → lat/lon for map pinpointing.

Falls back to legacy hardcoded extractor if Gemini is unavailable or API key missing.
"""

import json
import logging
import requests
from config import settings
from services.ner_extractor import extract_need_info  # legacy fallback

logger = logging.getLogger(__name__)

VALID_BIO_MARKERS = {
    "stagnant_water", "waterborne_risk", "vector_risk",
    "sanitation_failure", "water_supply",
    "respiratory_hazard", "animal_hazard", "waste_accumulation", "fever_cluster"
}
VALID_URGENCY = {"low", "medium", "high", "critical"}
VALID_CONFIDENCE = {"high", "medium", "low", "none"}


def _forward_geocode(query: str) -> tuple[float | None, float | None]:
    """
    Convert a place name to (lat, lon) using OpenStreetMap Nominatim.
    Biased to India. Returns (None, None) on failure.
    """
    if not query or query.lower().strip() in ("unknown", "", "none"):
        return None, None
    try:
        headers = {"User-Agent": "SevaAI-Platform/1.0 (bio-risk-intelligence)"}
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": query,
                "format": "json",
                "limit": 1,
                "countrycodes": "IN",
                "addressdetails": 0,
            },
            headers=headers,
            timeout=6,
        )
        resp.raise_for_status()
        results = resp.json()
        if results:
            lat, lon = float(results[0]["lat"]), float(results[0]["lon"])
            logger.info(f"Geocoded '{query}' → ({lat}, {lon})")
            return lat, lon
        else:
            logger.warning(f"Nominatim returned no results for '{query}'")
    except Exception as e:
        logger.warning(f"Forward geocoding failed for '{query}': {e}")
    return None, None


GEMINI_PROMPT = """You are an expert geolocation extraction engine and bio-risk analyst specialized in Indian languages, particularly Hinglish (a mix of Hindi and English). Your job is to extract, verify, and geolocate place mentions from informal text inputs, as well as extract public health intelligence.

---
{text}
---

## PRECISION EXTRACTION RULES (MANDATORY)
You MUST extract location at the MOST GRANULAR level possible.
Extraction priority order (most specific = best):
  Level 1 (BEST)   → Street / Road name       e.g. "90 Feet Road"
  Level 2          → Locality / Chawl / Block  e.g. "Koliwada section"
  Level 3          → Neighbourhood / Zone      e.g. "Dharavi"
  Level 4          → District / Tehsil         e.g. "Kurla"
  Level 5 (WORST)  → City only                 e.g. "Mumbai"

RULE: If you only return a city name, your extraction has FAILED.
City-only output is only acceptable when zero sub-area info exists.

## HINGLISH LOCATION PARSING RULES
In Hinglish sentences, location names appear BEFORE grammar particles.
Grammar particles to strip away — these are NOT part of the place name:
  - "mein"   (in)
  - "se"     (from)
  - "ke paas" (near)
  - "par"    (on/at)
  - "wala"   (the one near)
  - "ke andar" (inside)
  - "ke bahar" (outside)
  - "ke saamne" (in front of)
  - "ke peeche" (behind)

EXAMPLES of correct entity boundary detection:
  ❌ WRONG: "Mumbai mein"  → extracts "Mumbai mein"
  ✅ RIGHT: "Mumbai mein"  → extracts "Mumbai" (strip "mein")
  ❌ WRONG: "Dharavi, Mumbai mein Koliwada section se" → extracts only "Mumbai"
  ✅ RIGHT: Same text → extracts: primary = "Koliwada section", area = "Dharavi", city = "Mumbai"

## RELATIVE LANDMARK EXTRACTION
Even if a place has no official name, extract it as a relative_landmark for field teams. These phrases are valid:
  - "pump ke paas"         → near water pump
  - "overhead tank ke paas" → near overhead tank
  - "chawl ke andar"       → inside chawl building
  - "nale ke bagal mein"   → beside the drain

## URGENCY & BIO-MARKER RULES
• Urgency -> critical: 3+ people sick, epidemic words; high: drainage failure, sewage overflow; medium: water quality complaint; low: general sanitation.
• Bio-Markers MUST be from this exact list: stagnant_water, waterborne_risk, vector_risk, sanitation_failure, water_supply, respiratory_hazard, animal_hazard, waste_accumulation, fever_cluster

## REQUIRED OUTPUT STRUCTURE
Always respond with the following JSON structure and nothing else:

{{
  "extraction_level": "street | locality | neighbourhood | city",
  "primary_location": "<most specific place found>",
  "area": "<neighbourhood / zone>",
  "city": "<city>",
  "state": "<state>",
  "relative_landmark": "<nearby unnamed reference if any>",
  "full_address_reconstructed": "<human readable full address>",
  "latitude": <most granular lat possible or null>,
  "longitude": <most granular lng possible or null>,
  "confidence": "high | medium | low",
  "extraction_warning": "<null, or reason if city-only>",

  "extracted_need": "<one clear English sentence summarising the core public health problem>",
  "urgency_level": "<low | medium | high | critical>",
  "bio_markers_detected": ["<zero or more from ONLY the valid list>"],
  "language_detected": "<hindi | english | mixed>"
}}
"""


def extract_with_gemini(text: str) -> dict:
    """
    Calls Gemini (google-genai SDK) in a single prompt to extract all NER fields
    + confidence-gated forward geocoding via Nominatim.
    Falls back to legacy regex extractor on any failure.
    """
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not configured — falling back to legacy NER")
        return _legacy_fallback(text)

    try:
        from google import genai  # type: ignore  # new SDK: pip install google-genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        prompt = GEMINI_PROMPT.format(text=text)

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        raw = response.text.strip()

        # Strip markdown fences if model misbehaves
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        parsed: dict = json.loads(raw)

        # ── Sanitise fields ──────────────────────────────────────────────
        primary_location = str(parsed.get("primary_location", "")).strip()
        area = str(parsed.get("area", "")).strip()
        city = parsed.get("city")
        state = parsed.get("state")

        # Build extracted_location logic
        loc_parts = [p for p in (primary_location, area, city) if p and p.lower() not in ("none", "null")]
        extracted_location = ", ".join(loc_parts)
        if not extracted_location:
            landmark = str(parsed.get("relative_landmark", "")).strip()
            extracted_location = landmark if landmark and landmark.lower() not in ("none", "null") else "Unknown"
        
        # Build geocodeable query using area/city/state
        geocode_parts = [p for p in (primary_location, area, city, state) if p and p.lower() not in ("none", "null")]
        geocodeable_location = ", ".join(geocode_parts)
        
        location_confidence = str(parsed.get("confidence", "none")).strip().lower()
        if location_confidence not in VALID_CONFIDENCE:
            location_confidence = "none"

        extracted_need = str(parsed.get("extracted_need", text[:160])).strip()

        urgency_level = str(parsed.get("urgency_level", "medium")).strip().lower()
        if urgency_level not in VALID_URGENCY:
            urgency_level = "medium"

        raw_markers = parsed.get("bio_markers_detected", [])
        bio_markers = [m for m in raw_markers if m in VALID_BIO_MARKERS]

        language_detected = str(parsed.get("language_detected", "mixed")).strip()

        # ── Geocoding gate ───────────────────────────────────────────────
        latitude = parsed.get("latitude")
        longitude = parsed.get("longitude")
        
        # If AI didn't provide coordinates or we have medium/low confidence, fallback to OpenStreetMap
        if not latitude or not longitude:
            if location_confidence in ("high", "medium") and geocodeable_location.lower() not in ("unknown", "", "none"):
                latitude, longitude = _forward_geocode(geocodeable_location)
                if latitude is None and extracted_location.lower() not in ("unknown", ""):
                    logger.info(f"Retrying geocode with display name: '{extracted_location}'")
                    latitude, longitude = _forward_geocode(extracted_location)
            elif location_confidence == "low" and geocodeable_location.lower() not in ("unknown", ""):
                latitude, longitude = _forward_geocode(geocodeable_location)

        logger.info(
            f"Gemini NER ✓ | display='{extracted_location}' | "
            f"query='{geocodeable_location}' | confidence={location_confidence} | "
            f"urgency={urgency_level} | markers={bio_markers} | "
            f"coords=({latitude}, {longitude})"
        )

        return {
            "extracted_location": extracted_location,
            "extracted_need": extracted_need,
            "urgency_level": urgency_level,
            "bio_markers_detected": bio_markers,
            "language_detected": language_detected,
            "latitude": latitude,
            "longitude": longitude,
        }

    except Exception as e:
        logger.error(f"Gemini NER failed ({type(e).__name__}: {e}) — falling back to legacy NER")
        return _legacy_fallback(text)


def _legacy_fallback(text: str) -> dict:
    """Regex-based NER with OpenStreetMap geocoding fallback."""
    result = extract_need_info(text)
    
    location = result.get("extracted_location")
    if location and location.lower() not in ("unknown", "", "none"):
        lat, lon = _forward_geocode(location)
        result["latitude"] = lat
        result["longitude"] = lon
    else:
        result["latitude"] = None
        result["longitude"] = None
        
    return result
