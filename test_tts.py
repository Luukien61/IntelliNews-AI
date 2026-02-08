#!/usr/bin/env python3
"""TTS test: gen .wav → upload MinIO → xóa local → trả về kết quả của synthesize()."""
import logging
import json

logging.basicConfig(level=logging.INFO)


def test_tts(
    text: str,
    voice_id: str = None,
    upload_to_s3: bool = True,
):
    """
    Gen speech từ text, upload lên MinIO (S3), xóa file local, trả về đúng dict của synthesize().

    Args:
        text: Câu tiếng Việt cần tổng hợp.
        voice_id: Voice ID (vd 'Binh', 'Doan'). None = dùng default.
        upload_to_s3: True = upload MinIO và xóa local (mặc định).

    Returns:
        Dict trả về từ services.tts.service.tts_service.synthesize():
        - filename, s3_key, s3_url, presigned_url (khi upload_to_s3=True)
        - hoặc filename, local_path (khi upload_to_s3=False)
    """
    from services.tts.service import tts_service

    print("Available voices:")
    for desc, name in tts_service.list_voices():
        print(f"   - {desc} (ID: {name})")
    print()

    if voice_id:
        print(f"Using voice: {voice_id}")
    else:
        print("Using default voice")
    print(f"Text: {text[:100]}{'...' if len(text) > 100 else ''}")
    print(f"Upload to S3 (MinIO): {upload_to_s3}")
    print("Generating...")

    result = tts_service.synthesize(
        text=text,
        voice_id=voice_id,
        upload_to_s3=upload_to_s3,
    )

    print("\n" + "=" * 60)
    print("✓ Generation Complete!")
    print("=" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if "s3_url" in result:
        print(f"\n📦 S3 key: {result['s3_key']}")
        print(f"🔗 S3 URL: {result['s3_url']}")
        print(f"🔗 Presigned (24h): {result['presigned_url']}")
    elif "local_path" in result:
        print(f"\n📁 Local file: {result['local_path']}")

    return result


if __name__ == "__main__":
    # Mặc định: gen .wav → upload MinIO → xóa local → trả về dict của synthesize()
    print("=== TTS: Generate → Upload MinIO → Delete local ===\n")
    result = test_tts(
        "Từng được xem là bảo chứng phòng vé của điện ảnh Hong Kong (Trung Quốc) suốt hơn hai thập niên, "
        "Cổ Thiên Lạc bước vào năm 2026 với một dự án mang nhiều kỳ vọng - bản điện ảnh Tầm Tần ký, "
        "hậu truyện của series kinh điển Cỗ máy thời gian.",
        upload_to_s3=True,
    )
    # result chính là dict mà synthesize() trả về (filename, s3_key, s3_url, presigned_url)
