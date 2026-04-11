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
    "sanitation_failure", "water_supply"
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


GEMINI_PROMPT = """You are an AI analyst for SevaAI, a bio-risk field intelligence platform in India.

A field coordinator has submitted this voice/text report. It may be in Hindi (Romanized), English, or mixed:

---
{text}
---

Your job: extract structured intelligence. Return a SINGLE valid JSON object — no markdown, no explanation, just the JSON.

{{
  "extracted_location": "<display name of the specific place — neighbourhood, colony, mohalla, landmark, village, city>",
  "geocodeable_location": "<OpenStreetMap-ready search query, always include city/state if known, e.g. 'Hauz Khas, New Delhi' or 'Dharavi, Mumbai' or 'Sector 15, Noida, Uttar Pradesh'>",
  "location_confidence": "<high | medium | low | none>",
  "extracted_need": "<one clear English sentence summarising the core public health problem>",
  "urgency_level": "<low | medium | high | critical>",
  "bio_markers_detected": ["<zero or more from ONLY this list: stagnant_water, waterborne_risk, vector_risk, sanitation_failure, water_supply>"],
  "language_detected": "<hindi | english | mixed>"
}}

━━━ LOCATION RULES ━━━

STEP 1 — Extract the place:
• Accept well-known Indian place names in any script variant: "Hauz Khas", "Lajpat Nagar", "Govindpuri", "Dharavi", "Saket", "Tilak Nagar", "Sector 22 Noida", etc.
• Hindi Romanized forms are valid: "Hauz khas", "lal kuan", "govindpuri", "najafgarh"
• Extract the MOST SPECIFIC geographic name: colony > area > city

STEP 2 — Verify it is a real Indian location:
• Ask yourself: "Would this appear as a named place on Google Maps or OpenStreetMap in India?"
• Famous Indian areas ALWAYS get confidence=high: Hauz Khas, Connaught Place, Dharavi, Lajpat Nagar, Sarojini Nagar, Karol Bagh, Andheri, etc.
• Tier-2 city areas get confidence=medium: known colonies, sectors, villages in smaller cities
• HARD REJECT — these are NEVER places: "yahan", "wahan", "yha", "mai", "kal", "aaj", "pump", "naali", "ghar", "paas", "ke", "se", "mein", "hai"
• If ONLY rejected words exist → extracted_location="Unknown", geocodeable_location="Unknown", confidence=none

STEP 3 — Format geocodeable_location for OpenStreetMap:
• Always add city/state context: "Hauz Khas, New Delhi" NOT just "Hauz Khas"
• Use English spellings for the geocode query (not transliterated forms): "Lal Kuan, Delhi" not "lal kuan"
• If city is unknown but state can be inferred, add state
• geocodeable_location must be the best possible search string to find this on a map

━━━ URGENCY RULES ━━━
• critical: 3+ people sick/affected, children sick, days without water, epidemic words (cholera, dengue outbreak), emergency
• high: drainage failure, sewage overflow, stagnant water near residential area, fever spreading
• medium: water quality complaint, single sick person, blocked drain reported
• low: general sanitation concern, preventive alert

━━━ BIO MARKER RULES ━━━
stagnant_water → standing water, naali band, ruka hua paani, blocked drain, paani ruka
waterborne_risk → diarrhea, loose motions, vomiting, stomach pain, pet dard, ulti, cholera
vector_risk → mosquitoes, machhar, machar, rats, chuhe, foul smell, badbu, dengue, malaria
sanitation_failure → open defecation, sewage overflow, naali uf rahi, dirty water, ganda paani
water_supply → no water, paani nahi, handpump broken, handpump kharab, no drinking water

Return ONLY the JSON. No ```json. No extra text."""


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
        extracted_location = str(parsed.get("extracted_location", "Unknown")).strip()
        geocodeable_location = str(parsed.get("geocodeable_location", extracted_location)).strip()
        location_confidence = parsed.get("location_confidence", "none")
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
        latitude, longitude = None, None
        if location_confidence in ("high", "medium") and geocodeable_location.lower() not in ("unknown", "", "none"):
            latitude, longitude = _forward_geocode(geocodeable_location)
            # If the AI-formatted query fails, try the raw display name as fallback
            if latitude is None and extracted_location.lower() not in ("unknown", ""):
                logger.info(f"Retrying geocode with display name: '{extracted_location}'")
                latitude, longitude = _forward_geocode(extracted_location)
        elif location_confidence == "low" and geocodeable_location.lower() not in ("unknown", ""):
            # Try anyway for low confidence — better than no coords
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
    """Regex-based NER with no geocoding."""
    result = extract_need_info(text)
    result["latitude"] = None
    result["longitude"] = None
    return result
