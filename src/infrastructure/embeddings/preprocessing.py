"""
Arabic text preprocessing for embeddings.

Handles Arabic-specific text normalization, diacritics removal,
and query expansion for better embedding quality.
"""

import re
from typing import Any


class ArabicTextPreprocessor:
    """
    Preprocess Arabic text for embedding generation.

    Normalizes text to improve embedding consistency:
    - Removes diacritics (tashkeel)
    - Normalizes alef variants
    - Removes tatweel (kashida)
    - Normalizes ta marbuta and ha
    - Cleans whitespace
    """

    # Arabic diacritics (tashkeel)
    DIACRITICS_PATTERN = re.compile(
        "[\u0610-\u061A]"  # Arabic diacritics
        "|[\u064B-\u065F]"  # Arabic hamza below/above
        "|[\u0670]"         # superscript alef
        "|[\u06D6-\u06DC]"  # Quranic marks
        "|[\u06DF-\u06E4]"
        "|[\u06E7-\u06E8]"
        "|[\u06EA-\u06ED]"
    )

    # Tatweel (kashida)
    TATWEEL_PATTERN = re.compile("\u0640")

    # Alef variants → alef
    ALEF_PATTERN = re.compile("[\u0622\u0623\u0625\u0671]")

    # Ta marbuta → ha
    TA_MARBUTA_PATTERN = re.compile("\u0629")

    # Extra whitespace
    WHITESPACE_PATTERN = re.compile(r"\s+")

    # Arabic question mark
    ARABIC_QUESTION = re.compile("؟")

    def normalize(self, text: str) -> str:
        """
        Normalize Arabic text for consistent embedding.

        Args:
            text: Raw Arabic text

        Returns:
            Normalized text.
        """
        if not text:
            return text

        # Remove diacritics
        text = self.DIACRITICS_PATTERN.sub("", text)

        # Remove tatweel
        text = self.TATWEEL_PATTERN.sub("", text)

        # Normalize alef variants
        text = self.ALEF_PATTERN.sub("\u0627", text)

        # Normalize ta marbuta to ha (optional, depends on use case)
        # text = self.TA_MARBUTA_PATTERN.sub("\u0647", text)

        # Normalize question marks
        text = self.ARABIC_QUESTION.sub("?", text)

        # Clean whitespace
        text = self.WHITESPACE_PATTERN.sub(" ", text).strip()

        return text

    def preprocess_for_embedding(self, text: str) -> str:
        """
        Full preprocessing pipeline for embedding.

        Normalizes and cleans text for optimal embedding quality.

        Args:
            text: Raw text (Arabic or mixed)

        Returns:
            Preprocessed text ready for embedding.
        """
        # Normalize
        text = self.normalize(text)

        # Remove URLs (they don't embed well)
        text = re.sub(r"https?://\S+", "", text)

        # Remove email addresses
        text = re.sub(r"\S+@\S+\.\S+", "", text)

        # Remove excessive punctuation
        text = re.sub(r"[!?.]{3,}", "...", text)

        # Final whitespace cleanup
        text = self.WHITESPACE_PATTERN.sub(" ", text).strip()

        return text

    def expand_query(self, query: str) -> str:
        """
        Expand short queries with context for better retrieval.

        Adds common Arabic stop words and context markers.

        Args:
            query: Short user query

        Returns:
            Expanded query.
        """
        # Don't expand already long queries
        if len(query.split()) > 5:
            return query

        # Common Arabic query patterns
        expansions = {
            "كم": "كم عدد",
            "ما": "ما هو",
            "أين": "أين يقع",
            "متى": "متى كان",
            "لماذا": "لماذا حدث",
            "كيف": "كيف يمكن",
        }

        words = query.split()
        if words and words[0] in expansions:
            words[0] = expansions[words[0]]
            return " ".join(words)

        return query


# Global preprocessor instance
arabic_preprocessor = ArabicTextPreprocessor()
