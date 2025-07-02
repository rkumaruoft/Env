import numpy as np
from typing import List
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class RelevancyIndex:
    """
    Computes a relevancy score (between 0 and 1) for a given text against a list of queries
    using sentence-transformer embeddings and cosine similarity.

    Usage:
        ri = RelevancyIndex(queries=[...])
        score = ri.score_text(text)
    """

    def __init__(
        self,
        queries: List[str],
        model_name: str = "all-MiniLM-L6-v2",
        num_chunks: int = 5
    ):
        if not queries:
            raise ValueError("Query list cannot be empty.")

        self.queries = queries
        self.model = SentenceTransformer(model_name)
        self.num_chunks = num_chunks
        self.query_embeds = self.model.encode(
            queries, convert_to_numpy=True, show_progress_bar=False
        )

    @staticmethod
    def chunk_text_to_n(self, text: str, n: int) -> List[str]:
        """Split the input text into `n` chunks of approximately equal word count."""
        words = text.split()
        total = len(words)
        if total == 0 or n <= 0:
            return []
        size = (total + n - 1) // n
        return [" ".join(words[i * size:min((i + 1) * size, total)]) for i in range(n)]

    def score_text(self, text: str) -> float:
        """
        Compute the relevancy score for the given text.

        Args:
            text (str): Input text to evaluate.

        Returns:
            float: Relevancy score between 0 and 1.
        """
        chunks = self.chunk_text_to_n(text, self.num_chunks)
        if not chunks:
            return 0.0

        chunk_embeds = self.model.encode(
            chunks, convert_to_numpy=True, show_progress_bar=False
        )
        sims = cosine_similarity(self.query_embeds, chunk_embeds)
        return float(sims.max(axis=1).mean())
