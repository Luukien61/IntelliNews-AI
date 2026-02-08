#!/usr/bin/env python3
"""Simple TTS Test"""
import logging

logging.basicConfig(level=logging.INFO)


def test_tts(text: str, voice_id: str = None):
    """
    Generate speech from text.
    
    Args:
        text: Vietnamese text to synthesize
        voice_id: Voice ID string (e.g., 'Binh', 'Doan', etc.). If None, uses default voice.
    
    Returns:
        Path to generated audio file
    """
    from services.tts.service import tts_service
    
    # List available voices first
    print("Available voices:")
    available_voices = tts_service.list_voices()
    for desc, name in available_voices:
        print(f"   - {desc} (ID: {name})")
    print()
    
    # Use specified voice or default
    if voice_id:
        print(f"Using voice: {voice_id}")
    else:
        print("Using default voice (first available)")
    
    print(f"Text: {text}")
    print("Generating...")
    
    audio_path = tts_service.synthesize(text=text, voice_id=voice_id)
    
    print(f"✓ Done: {audio_path}")
    return audio_path


if __name__ == "__main__":
    # Test với voice mặc định
    print("=== Test 1: Default voice ===")
    test_tts("Từng được xem là bảo chứng phòng vé của điện ảnh Hong Kong (Trung Quốc) suốt hơn hai thập niên, Cổ Thiên Lạc bước vào năm 2026 với một dự án mang nhiều kỳ vọng - bản điện ảnh Tầm Tần ký, hậu truyện của series kinh điển Cỗ máy thời gian. Nhưng trái với không khí háo hức ban đầu, hành trình của bộ phim tại Việt Nam lại diễn ra khá lặng lẽ khiến nhiều khán giả cho rằng sức hút của Cổ Thiên Lạc phiên bản “ông chú” đã bị thời gian bào mòn.")
    
    print("\n=== Test 2: Specific voice (Doan) ===")
    test_tts("Chào bạn, tôi đang nói bằng giọng của bác sĩ Tuyên.", voice_id="Doan")
