"""ViT5-based abstractive summarizer for Vietnamese news (summary_short)."""
import logging
import re

import torch
from transformers import AutoTokenizer, T5ForConditionalGeneration

from config import settings
from .base_summarizer import BaseSummarizer, clean_text
from .summary_postprocess import count_filler_hits, postprocess_abstractive_summary

logger = logging.getLogger(__name__)

# VietAI/vit5-base-vietnews-summarization: no task prefix; append </s> to input (model card).
_EOS_SUFFIX = "</s>"


class ViT5Summarizer(BaseSummarizer):
    """
    Abstractive summarizer using VietAI ViT5 fine-tuned on vietnews.

    Official usage: raw article text + EOS suffix, beam search, no ``summarize:`` prefix.
    Result is stored in ``summary_short``.
    """

    def __init__(
        self,
        model_name: str = "VietAI/vit5-base-vietnews-summarization",
        device: str = None,
        min_length: int | None = None,
        max_length: int | None = None,
    ):
        super().__init__(name="ViT5")
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.min_length = min_length if min_length is not None else settings.vit5_min_length
        self.max_length = max_length if max_length is not None else settings.vit5_max_length
        self.num_beams = settings.vit5_num_beams
        self.length_penalty = settings.vit5_length_penalty
        self.max_input_chars = settings.vit5_max_input_chars
        self.max_filler_hits = settings.vit5_max_filler_hits

        logger.info(
            "Initializing ViT5 on %s (min_len=%s, max_len=%s, max_input_chars=%s)",
            self.device,
            self.min_length,
            self.max_length,
            self.max_input_chars,
        )

        self.model_name = model_name
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = T5ForConditionalGeneration.from_pretrained(
                self.model_name,
                low_cpu_mem_usage=False,
            ).to(self.device)
            self.model.eval()
            logger.info("Successfully loaded ViT5 model: %s", self.model_name)
        except Exception as e:
            logger.warning("Error loading ViT5 model %s: %s", self.model_name, e)
            self.model_name = "VietAI/vit5-base"
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = T5ForConditionalGeneration.from_pretrained(
                self.model_name,
                low_cpu_mem_usage=False,
            ).to(self.device)
            self.model.eval()
            logger.info("Using fallback ViT5 base model")

        self._bad_words_ids = self._build_bad_words_ids()

    def _build_bad_words_ids(self) -> list[list[int]] | None:
        """Token ids to discourage during generation (fillers)."""
        candidates = ["ờ", " à", "à ", "ừm", " uh", " um"]
        bad: list[list[int]] = []
        for word in candidates:
            try:
                ids = self.tokenizer.encode(word, add_special_tokens=False)
                if ids:
                    bad.append(ids)
            except Exception:
                continue
        return bad or None

    def _prepare_input(self, text: str) -> str:
        """
        Preprocess article body for ViT5.

        - Light clean (URLs, whitespace)
        - Truncate very long articles (lead-weighted for news)
        - Append EOS per VietAI model card (no ``summarize:`` / ``tóm tắt:`` prefix)
        """
        text = clean_text(text)
        if not text:
            return ""

        if len(text) > self.max_input_chars:
            head = text[: self.max_input_chars]
            last_stop = max(head.rfind("."), head.rfind("!"), head.rfind("?"))
            if last_stop > self.max_input_chars // 2:
                text = head[: last_stop + 1]
            else:
                text = head.rsplit(" ", 1)[0]

        eos = getattr(self.tokenizer, "eos_token", None) or _EOS_SUFFIX
        if eos and not text.endswith(eos):
            text = text + eos
        return text

    def _decode_generate(self, input_text: str, *, min_length: int, max_length: int) -> str:
        inputs = self.tokenizer(
            input_text,
            return_tensors="pt",
            max_length=1024,
            truncation=True,
            padding=False,
            add_special_tokens=True,
        ).to(self.device)

        gen_kwargs: dict = {
            "max_length": max_length,
            "min_length": min_length,
            "num_beams": self.num_beams,
            "length_penalty": self.length_penalty,
            "early_stopping": True,
            "no_repeat_ngram_size": 3,
            "do_sample": False,
        }
        if self._bad_words_ids:
            gen_kwargs["bad_words_ids"] = self._bad_words_ids

        with torch.no_grad():
            summary_ids = self.model.generate(
                inputs.input_ids,
                attention_mask=inputs.attention_mask,
                **gen_kwargs,
            )

        return self.tokenizer.decode(
            summary_ids[0],
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        )

    def _is_valid_vietnamese_output(self, text: str) -> bool:
        if not text or len(text.strip()) < 20:
            return False
        vietnamese_chars = (
            "abcdefghijklmnopqrstuvwxyz"
            "áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệ"
            "íìỉĩịóòỏõọôốồổỗộơớờởỡợ"
            "úùủũụưứừửữựýỳỷỹỵđ"
        )
        return any(c in text.lower() for c in vietnamese_chars)

    def summarize(self, text: str, ratio: float = 0.3) -> str:
        """
        Generate abstractive summary using ViT5.

        ``ratio`` is unused (interface compatibility); length is controlled by
        ``vit5_max_length`` / ``vit5_min_length`` in settings.
        """
        input_text = self._prepare_input(text)
        if not input_text:
            return "Không thể tạo tóm tắt."

        attempts = [
            (self.min_length, self.max_length),
            (max(15, self.min_length // 2), self.max_length),
            (15, min(self.max_length, 96)),
        ]

        best: str | None = None
        best_fillers = 10**9

        for min_len, max_len in attempts:
            try:
                decoded = self._decode_generate(input_text, min_length=min_len, max_length=max_len)
            except Exception as e:
                logger.warning("ViT5 generate failed (min=%s max=%s): %s", min_len, max_len, e)
                continue

            if not self._is_valid_vietnamese_output(decoded):
                continue

            processed = postprocess_abstractive_summary(decoded)
            fillers = count_filler_hits(processed)

            if fillers < best_fillers:
                best = processed
                best_fillers = fillers

            if fillers <= self.max_filler_hits and len(processed) >= 40:
                logger.info(
                    "ViT5 summary OK: %s chars, filler_hits=%s (min=%s max=%s)",
                    len(processed),
                    fillers,
                    min_len,
                    max_len,
                )
                return processed

        if best:
            logger.info(
                "ViT5 summary (best effort): %s chars, filler_hits=%s",
                len(best),
                best_fillers,
            )
            return best

        logger.warning("ViT5 could not produce a valid summary")
        return "Không thể tạo tóm tắt."
