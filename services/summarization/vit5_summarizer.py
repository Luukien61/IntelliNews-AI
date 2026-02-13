"""ViT5-based abstractive summarizer for Vietnamese text."""
import re
import logging

import torch
from transformers import AutoTokenizer, T5ForConditionalGeneration

from .base_summarizer import BaseSummarizer, clean_text

logger = logging.getLogger(__name__)


class ViT5Summarizer(BaseSummarizer):
    """
    Abstractive summarizer using VietAI's ViT5 model fine-tuned for
    Vietnamese news summarization.
    
    Uses beam search decoding with Vietnamese-specific post-processing.
    
    Result is saved to `summary_short` column.
    """

    def __init__(
        self,
        model_name: str = "VietAI/vit5-base-vietnews-summarization",
        device: str = None
    ):
        super().__init__(name="ViT5")
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Initializing ViT5 on {self.device}")

        self.model_name = model_name
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = T5ForConditionalGeneration.from_pretrained(
                self.model_name
            ).to(self.device)
            self.model.eval()
            logger.info(f"Successfully loaded ViT5 model: {self.model_name}")
        except Exception as e:
            logger.warning(f"Error loading ViT5 model {self.model_name}: {e}")
            # Fallback to base model
            self.model_name = "VietAI/vit5-base"
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = T5ForConditionalGeneration.from_pretrained(
                self.model_name
            ).to(self.device)
            self.model.eval()
            logger.info("Using fallback ViT5 base model")

    def _post_process(self, summary: str) -> str:
        """Clean up generated summary text."""
        # Remove invalid characters
        summary = re.sub(r'[^\x00-\x7F\u00C0-\u1EF9\s.,!?:;]', '', summary)
        # Fix spacing
        summary = re.sub(r'\s+', ' ', summary).strip()
        # Remove excessive repetition
        summary = re.sub(r'(.+?)\1{2,}', r'\1', summary)
        return summary

    def summarize(self, text: str, ratio: float = 0.3) -> str:
        """
        Generate abstractive summary using ViT5.

        Args:
            text: Input Vietnamese text
            ratio: Not used for abstractive summarization, kept for interface compatibility

        Returns:
            Summary string
        """
        text = clean_text(text)

        # Prompt formats to try (the fine-tuned model may expect different prefixes)
        prompt_formats = [
            f"summarize: {text}",
            f"tóm tắt: {text}",
            text,
        ]

        summary = "Không thể tạo tóm tắt (Unable to generate summary)"

        for prompt in prompt_formats:
            try:
                inputs = self.tokenizer(
                    prompt,
                    return_tensors="pt",
                    max_length=1024,
                    truncation=True,
                    padding="max_length",
                    add_special_tokens=True,
                ).to(self.device)

                with torch.no_grad():
                    summary_ids = self.model.generate(
                        inputs.input_ids,
                        attention_mask=inputs.attention_mask,
                        max_length=256,
                        min_length=30,
                        num_beams=4,
                        length_penalty=2.0,
                        early_stopping=True,
                        no_repeat_ngram_size=3,
                        do_sample=False,
                    )

                decoded = self.tokenizer.decode(
                    summary_ids[0],
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=True,
                )

                # Validate that the output contains Vietnamese/Latin characters
                vietnamese_chars = (
                    "abcdefghijklmnopqrstuvwxyz"
                    "áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệ"
                    "íìỉĩịóòỏõọôốồổỗộơớờởỡợ"
                    "úùủũụưứừửữựýỳỷỹỵđ"
                )
                if any(c in decoded.lower() for c in vietnamese_chars):
                    summary = decoded
                    break
            except Exception as e:
                logger.warning(f"Error with prompt format '{prompt[:30]}...': {e}")

        summary = self._post_process(summary)
        logger.info(f"ViT5 summary generated: {len(summary)} chars")
        return summary
