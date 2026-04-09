"""TF-IDF based extractive summarizer for Vietnamese text.

Suited for `summary_short`: selects 2–3 most keyword-rich sentences.
No ML model required – lightweight and fast.
"""
import logging

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .base_summarizer import BaseSummarizer, clean_text, sentence_tokenize

logger = logging.getLogger(__name__)


class TFIDFSummarizer(BaseSummarizer):
    """
    Extractive summarizer using TF-IDF sentence scoring.

    Each sentence is represented as a TF-IDF vector. Sentences are scored
    by their total cosine similarity to all other sentences (PageRank-like),
    so the most "central" (keyword-representative) sentences bubble up.

    Suitable for `summary_short`: with ratio=0.2 it extracts ~2 sentences
    that are richer than a title/description but still concise.
    """

    def __init__(self):
        super().__init__(name="TF-IDF")

    def summarize(self, text: str, ratio: float = 0.2) -> str:
        """
        Generate extractive summary using TF-IDF scoring.

        Args:
            text:  Input Vietnamese text.
            ratio: Fraction of sentences to include (default 0.2 → ~2 sentences
                   for a typical 10-sentence article).

        Returns:
            Summary string (sentences in their original order).
        """
        text = clean_text(text)
        sentences = sentence_tokenize(text)

        # For very short texts just return as-is
        if len(sentences) <= 3:
            return text

        # Build TF-IDF matrix (rows = sentences, columns = terms)
        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),   # unigrams + bigrams for better Vietnamese coverage
            max_df=0.95,          # ignore terms that appear in >95 % of sentences
            min_df=1,
            sublinear_tf=True,    # apply 1 + log(tf) to dampen term-frequency spikes
        )

        try:
            tfidf_matrix = vectorizer.fit_transform(sentences)
        except ValueError:
            # Degenerate case (all sentences identical, empty vocab, etc.)
            logger.warning("TF-IDF vectorizer failed – falling back to first sentences")
            num_fallback = max(1, int(len(sentences) * ratio))
            return " ".join(sentences[:num_fallback])

        # Sentence similarity matrix  (n × n)
        sim_matrix = cosine_similarity(tfidf_matrix)

        # Score = sum of similarities to every other sentence
        scores = sim_matrix.sum(axis=1)

        ranked_indices = np.argsort(scores)[::-1]
        num_sentences = max(2, int(len(sentences) * ratio))   # at least 2 sentences
        selected_indices = sorted(ranked_indices[:num_sentences])

        summary = " ".join(sentences[i] for i in selected_indices)
        logger.info(
            f"TF-IDF summary: {len(sentences)} sentences → {num_sentences} selected "
            f"({len(summary)} chars)"
        )
        return summary

