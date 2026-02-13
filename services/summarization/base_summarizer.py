"""Base summarizer and text utilities for Vietnamese text summarization."""
import re
import logging
from abc import ABC, abstractmethod


logger = logging.getLogger(__name__)

# Try to use underthesea for better Vietnamese sentence tokenization
try:
    from underthesea import sent_tokenize as _underthesea_sent_tokenize
    HAS_UNDERTHESEA = True
except ImportError:
    HAS_UNDERTHESEA = False
    logger.warning("underthesea not installed, using regex-based sentence tokenizer")


def clean_text(text: str) -> str:
    """Clean and normalize Vietnamese text."""
    text = re.sub(r'\s+', ' ', text.strip())
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    text = re.sub(r'\s+', ' ', text.strip())
    return text


def simple_sentence_tokenize(text: str) -> list[str]:
    """Simple regex-based sentence tokenizer for Vietnamese text."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def sentence_tokenize(text: str) -> list[str]:
    """Get the best available sentence tokenizer result."""
    if HAS_UNDERTHESEA:
        return _underthesea_sent_tokenize(text)
    return simple_sentence_tokenize(text)


class BaseSummarizer(ABC):
    """Abstract base class for all summarizers."""

    def __init__(self, name: str = "Base"):
        self.name = name

    @abstractmethod
    def summarize(self, text: str, ratio: float = 0.3) -> str:
        """
        Generate a summary of the input text.

        Args:
            text: Input text to summarize
            ratio: Ratio of sentences to keep (for extractive methods)

        Returns:
            Summary string
        """
        raise NotImplementedError("Each summarizer must implement this method")

    def __str__(self):
        return self.name
