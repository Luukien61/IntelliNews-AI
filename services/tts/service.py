import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
import hashlib

from config import settings

logger = logging.getLogger(__name__)


class TTSService:
    """
    Text-to-Speech service using VieNeu TTS model.
    Implements singleton pattern to load model only once.
    """

    _instance: Optional['TTSService'] = None
    _tts_model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize TTS service and load model if not already loaded."""
        if self._tts_model is None:
            self._load_model()

    def _load_model(self):
        """Load VieNeu TTS model."""
        try:
            logger.info(f"Loading VieNeu TTS model: {settings.tts_model_repo}")
            from vieneu import Vieneu

            # Initialize with specified GGUF model
            self._tts_model = Vieneu(backbone_repo=settings.tts_model_repo)
            logger.info("VieNeu TTS model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load TTS model: {str(e)}")
            raise RuntimeError(f"TTS model initialization failed: {str(e)}")

    def generate_filename(self, text: str) -> str:
        """
        Generate unique filename for audio output.
        
        Args:
            text: Input text (used for hash)
            
        Returns:
            Unique filename with timestamp and hash
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        return f"tts_{timestamp}_{text_hash}.wav"

    def list_voices(self) -> list[tuple[str, str]]:
        """
        List all available preset voices.
        
        Returns:
            List of tuples containing (description, voice_id)
        """
        try:
            available_voices = self._tts_model.list_preset_voices()
            logger.info(f"Available voices: {len(available_voices)}")
            return available_voices
        except Exception as e:
            logger.error(f"Failed to list voices: {str(e)}")
            return []

    def synthesize(
            self,
            text: str,
            voice_id: Optional[str] = None,
            ref_audio: Optional[str] = None,
            ref_text: Optional[str] = None
    ) -> str:
        """
        Convert text to speech and save to file.
        
        Args:
            text: Text to convert to speech
            voice_id: Optional ID of preset voice to use (e.g., 'Binh', 'Doan')
            ref_audio: Optional path to reference audio for voice cloning
            ref_text: Optional text spoken in reference audio
            
        Returns:
            Path to generated audio file
            
        Raises:
            RuntimeError: If synthesis fails
        """
        try:
            logger.info(f"Synthesizing text: {text[:50]}...")

            # Generate audio
            if ref_audio and ref_text:
                logger.info(f"Using voice cloning with reference audio: {ref_audio}")
                audio = self._tts_model.infer(
                    text=text,
                    ref_audio=ref_audio,
                    ref_text=ref_text
                )
            else:
                # Use specified voice_id or default voice from settings
                if voice_id:
                    logger.info(f"Using preset voice: {voice_id}")
                    voice_data = self._tts_model.get_preset_voice(voice_id)
                else:
                    # Use default voice from settings
                    default_voice_id = settings.default_tts_voice
                    logger.info(f"Using default voice from settings: {default_voice_id}")
                    try:
                        voice_data = self._tts_model.get_preset_voice(default_voice_id)
                    except Exception as e:
                        logger.warning(f"Failed to load configured default voice '{default_voice_id}': {e}")
                        # Fallback to first available voice
                        available_voices = self.list_voices()
                        if available_voices:
                            _, fallback_voice_id = available_voices[0]
                            logger.info(f"Falling back to first available voice: {fallback_voice_id}")
                            voice_data = self._tts_model.get_preset_voice(fallback_voice_id)
                        else:
                            raise RuntimeError("No preset voices available")
                
                audio = self._tts_model.infer(text=text, voice=voice_data)

            # Generate filename and save
            filename = self.generate_filename(text)
            output_path = settings.tts_output_path / filename

            logger.info(f"Saving audio to: {output_path}")
            self._tts_model.save(audio, str(output_path))

            logger.info(f"Audio generated successfully: {filename}")
            return str(output_path)

        except Exception as e:
            logger.error(f"TTS synthesis failed: {str(e)}")
            raise RuntimeError(f"Failed to generate speech: {str(e)}")

    def get_audio_path(self, filename: str) -> Optional[Path]:
        """
        Get full path to audio file if it exists.
        
        Args:
            filename: Audio filename
            
        Returns:
            Path to audio file or None if not found
        """
        file_path = settings.tts_output_path / filename
        if file_path.exists() and file_path.is_file():
            return file_path
        return None


# Global service instance
tts_service = TTSService()
