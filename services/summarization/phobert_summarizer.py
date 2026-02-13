"""PhoBERT-based extractive summarizer for Vietnamese text."""
import logging

import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel
from sklearn.metrics.pairwise import cosine_similarity

from .base_summarizer import BaseSummarizer, clean_text, sentence_tokenize

logger = logging.getLogger(__name__)


class PhoBERTSummarizer(BaseSummarizer):
    """
    Extractive summarizer using VietAI's PhoBERT.
    
    Uses sentence embeddings from PhoBERT [CLS] token and ranks sentences
    by cosine similarity (PageRank-like scoring). Selected top sentences
    are returned in their original order.
    
    Result is saved to `summary_default` column.
    """

    def __init__(self, model_name: str = "vinai/phobert-base", device: str = None):
        super().__init__(name="PhoBERT (VietAI)")
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Initializing PhoBERT on {self.device}")

        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModel.from_pretrained(self.model_name).to(self.device)
        self.model.eval()
        logger.info("PhoBERT model loaded successfully")

    def _get_sentence_embeddings(self, sentences: list[str]) -> np.ndarray:
        """Get [CLS] token embeddings for each sentence."""
        embeddings = []
        for sentence in sentences:
            inputs = self.tokenizer(
                sentence,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=256
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)

            # Use the [CLS] token embedding as the sentence embedding
            sentence_embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()
            embeddings.append(sentence_embedding[0])

        return np.array(embeddings)

    def summarize(self, text: str, ratio: float = 0.3) -> str:
        """
        Generate extractive summary using PhoBERT embeddings.

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

        # Get sentence embeddings
        embeddings = self._get_sentence_embeddings(sentences)

        # Compute cosine similarity between sentences
        sim_matrix = cosine_similarity(embeddings)

        # Score sentences using PageRank-like algorithm
        scores = np.sum(sim_matrix, axis=1)
        ranked_indices = sorted(
            range(len(sentences)),
            key=lambda i: scores[i],
            reverse=True
        )

        # Select top sentences and preserve original order
        num_sentences = max(1, int(len(sentences) * ratio))
        selected_indices = sorted(ranked_indices[:num_sentences])

        summary = " ".join([sentences[i] for i in selected_indices])
        logger.info(
            f"PhoBERT summary: {len(sentences)} sentences → {num_sentences} selected"
        )
        return summary
