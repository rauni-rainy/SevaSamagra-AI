import logging
import requests
import os
import tempfile
import google.generativeai as genai
from config import settings

logger = logging.getLogger(__name__)

def transcribe_audio(audio_url: str) -> str:
    """
    Downloads audio from a Twilio recording URL and transcribes it using Google Gemini 1.5.
    
    Args:
        audio_url (str): The URL of the recorded audio provided by Twilio.
        
    Returns:
        str: The transcribed text. Returns an empty string if transcription fails.
    """
    logger.info(f"Received audio URL for transcription: {audio_url}")
    
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not configured.")
        return ""
        
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.error("Twilio credentials not configured.")
        return ""

    try:
        # 1. Download audio file using Twilio credentials
        auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        # Twilio audio extensions, usually .wav or .mp3, let's just append .mp3
        download_url = f"{audio_url}.mp3"
        response = requests.get(download_url, auth=auth, timeout=15)
        response.raise_for_status()
        
        audio_content = response.content
        if not audio_content:
            logger.error("Downloaded audio file is empty.")
            return ""

        # 2. Transcribe via Gemini
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # We need a physical file to upload via Gemini API
        fd, temp_path = tempfile.mkstemp(suffix=".mp3")
        with os.fdopen(fd, 'wb') as f:
            f.write(audio_content)
            
        try:
            # Upload to Gemini File API
            sample_file = genai.upload_file(path=temp_path)
            
            # Use gemini-1.5-flash for audio transcription (fast and efficient)
            model = genai.GenerativeModel('models/gemini-1.5-flash')
            
            # Generate content asking for transcription
            result = model.generate_content([
                sample_file, 
                "Transcribe this audio exactly as you hear it. Provide only the transcription and no extra text."
            ])
            text = result.text.strip()
            
            # Clean up the file from Gemini
            try:
                sample_file.delete()
            except Exception as e:
                logger.warning(f"Failed to delete file from Gemini API: {e}")
                
        finally:
            # Clean up the local temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)

        logger.info(f"Transcription successful. Length: {len(text)} characters.")
        return text
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error downloading audio: {e}")
        return ""
    except Exception as e:
        logger.error(f"API failure during transcription: {e}")
        return ""
