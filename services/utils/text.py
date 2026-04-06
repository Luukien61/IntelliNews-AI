import re
import html
import unicodedata

RE_HTML_TAG = re.compile(r'<[^>]+>')
RE_WHITESPACE = re.compile(r'\s+')
RE_EMOJI = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE
)
RE_PUNCTUATION = re.compile(r'\s*([,.:;!?])\s*')


def clean_text_for_ai(text: str, remove_emoji: bool = True) -> str:
    """
    Làm sạch văn bản tiếng Việt để dùng cho Embeddings, Summarization, TTS.

    Args:
        text: Văn bản đầu vào.
        remove_emoji: Có xóa emoji không (Khuyên dùng True cho TTS/Summarization).

    Returns:
        Văn bản đã chuẩn hóa.
    """
    if not text or not isinstance(text, str):
        return ""

    text = html.unescape(text)

    text = RE_HTML_TAG.sub(' ', text)

    # 3. Chuẩn hóa Unicode (NFC)
    # Quan trọng với tiếng Việt: gộp ký tự gốc + dấu thành 1 ký tự duy nhất (à thay vì a + `)
    text = unicodedata.normalize('NFC', text)

    # 4. Xóa Emoji (Tùy chọn)
    if remove_emoji:
        text = RE_EMOJI.sub('', text)

    # 5. Xóa ký tự điều khiển (Control characters)
    # Giữ lại space, nhưng xóa các ký tự ẩn khác
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch == ' ')

    # 6. Xử lý khoảng trắng đặc biệt (zero-width, non-breaking)
    text = text.replace('\u200b', '').replace('\xa0', ' ')

    # 7. Chuẩn hóa khoảng trắng quanh dấu câu (Tiếng Việt)
    # Biến "Xin chào , tôi" thành "Xin chào, tôi"
    # Lưu ý: Regex này có thể ảnh hưởng số thập phân (3.14), cần cân nhắc ngữ cảnh
    # Ở đây ta ưu tiên văn bản tự nhiên, số thập phân thường ít gặp trong text thuần
    text = RE_PUNCTUATION.sub(r'\1 ', text)

    # 8. Gom nhiều khoảng trắng thành 1 và xóa 2 đầu
    text = RE_WHITESPACE.sub(' ', text)

    return text.strip()