"""Position-based extractive summarizer for Vietnamese text."""
import logging

from .base_summarizer import BaseSummarizer, clean_text, sentence_tokenize

logger = logging.getLogger(__name__)


class PositionSummarizer(BaseSummarizer):
    """
    Lightweight extractive summarizer that scores sentences by position.
    
    First sentences are considered most important (lead bias common in news).
    No ML model needed — can serve as a fast fallback or baseline.
    """

    def __init__(self):
        super().__init__(name="Position-based")

    def summarize(self, text: str, ratio: float = 0.3) -> str:
        """
        Generate extractive summary based on sentence position.

        Args:
            text: Input Vietnamese text
            ratio: Fraction of sentences to include in summary

        Returns:
            Summary string
        """
        text = clean_text(text)
        sentences = sentence_tokenize(text)

        if len(sentences) <= 2:
            return text

        # Score sentences: earlier = higher score
        num_sent = len(sentences)
        scores = [1.0 - (i / num_sent) for i in range(num_sent)]

        # Rank by score
        ranked_indices = sorted(
            range(num_sent),
            key=lambda i: scores[i],
            reverse=True
        )

        # Select top sentences and preserve original order
        num_sentences = max(1, int(num_sent * ratio))
        selected_indices = sorted(ranked_indices[:num_sentences])

        summary = " ".join([sentences[i] for i in selected_indices])
        logger.info(
            f"Position summary: {num_sent} sentences → {num_sentences} selected"
        )
        return summary
