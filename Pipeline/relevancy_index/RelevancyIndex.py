import os
import sys
import io
from typing import List, Optional

import requests
import PyPDF2
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

class RelevancyIndex:
    """
    Download PDFs, split text into chunks, embed against queries, compute relevancy indices, and plot results.

    Supports input files in .txt or .csv formats (with one URL per line or one URL column).

    Args:
        input_file: Path to a .txt or .csv file containing PDF URLs.
        queries_file: Path to a .txt file with one query per line.
        output_csv: Path to save overall scores CSV (or None to only print).
        model_name: SentenceTransformer model name.
        num_chunks: Number of equal-sized text chunks per PDF.
        csv_url_column: Column name in CSV for URLs. If None, uses the first column.
        enable_plot: Whether to display the heatmap plot (default True).
    """

    def __init__(
        self,
        input_file: str,
        queries_file: str,
        output_csv: Optional[str] = None,
        model_name: str = "all-MiniLM-L6-v2",
        num_chunks: int = 5,
        csv_url_column: Optional[str] = None,
        enable_plot: bool = True,
    ):
        self.input_file = input_file
        self.queries_file = queries_file
        self.output_csv = output_csv
        self.model_name = model_name
        self.num_chunks = num_chunks
        self.csv_url_column = csv_url_column
        self.enable_plot = enable_plot

        # placeholders for later
        self.urls: List[str] = []
        self.queries: List[str] = []
        self.query_embeds: np.ndarray = np.array([])
        self.model: SentenceTransformer = None  # type: ignore
        self.results: List[tuple] = []
        self.per_pdf_query_scores: List[np.ndarray] = []

    @staticmethod
    def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
        text_chunks: List[str] = []
        try:
            with io.BytesIO(pdf_bytes) as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    text_chunks.append(page_text)
        except Exception as e:
            print(f"Warning: could not parse PDF: {e}", file=sys.stderr)
            return ""
        return "\n".join(text_chunks)

    @staticmethod
    def chunk_text_to_n(text: str, n: int) -> List[str]:
        words = text.split()
        total = len(words)
        if total == 0 or n <= 0:
            return []
        size = (total + n - 1) // n
        chunks = []
        for i in range(n):
            start = i * size
            end = min(start + size, total)
            if start >= total:
                break
            chunks.append(" ".join(words[start:end]))
        return chunks

    @staticmethod
    def load_queries(path: str) -> List[str]:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Queries file not found: {path}")
        queries: List[str] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                q = line.strip()
                if q:
                    queries.append(q)
        return queries

    def load_urls(self) -> None:
        if not os.path.isfile(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        ext = os.path.splitext(self.input_file)[1].lower()
        if ext == ".txt":
            with open(self.input_file, "r", encoding="utf-8") as f:
                self.urls = [line.strip() for line in f if line.strip()]
        elif ext == ".csv":
            df = pd.read_csv(self.input_file)
            if self.csv_url_column and self.csv_url_column in df.columns:
                self.urls = df[self.csv_url_column].dropna().astype(str).tolist()
            else:
                col = df.columns[0]
                self.urls = df[col].dropna().astype(str).tolist()
        else:
            raise ValueError("Unsupported input file type: must be .txt or .csv")
        if not self.urls:
            raise ValueError(f"No URLs found in: {self.input_file}")

    def initialize_model(self) -> None:
        print(f"Loading model '{self.model_name}'...")
        self.model = SentenceTransformer(self.model_name)
        print("Embedding queries...")
        self.query_embeds = self.model.encode(
            self.queries,
            convert_to_numpy=True,
            show_progress_bar=False
        )

    def process_pdf(self, url: str) -> None:
        print(f"Downloading {url}...", end="", flush=True)
        try:
            resp = requests.get(url)
            resp.raise_for_status()
            pdf_bytes = resp.content
        except Exception as e:
            print(f" failed: {e}")
            return

        text = self.extract_text_from_pdf_bytes(pdf_bytes)
        chunks = self.chunk_text_to_n(text, self.num_chunks)
        if not chunks:
            scores = np.zeros(len(self.queries))
            relevancy = 0.0
        else:
            chunk_embeds = self.model.encode(
                chunks,
                convert_to_numpy=True,
                show_progress_bar=False
            )
            sims = cosine_similarity(self.query_embeds, chunk_embeds)
            scores = sims.max(axis=1)
            relevancy = float(scores.mean())

        self.per_pdf_query_scores.append(scores)
        self.results.append((url, relevancy))
        print(f" relevancy = {relevancy:.4f}")

    def save_results(self) -> None:
        df = pd.DataFrame(
            self.results,
            columns=["pdf_url", "relevancy_index"]
        ).sort_values(
            "relevancy_index", ascending=False
        ).reset_index(drop=True)

        if self.output_csv:
            df.to_csv(self.output_csv, index=False)
            print(f"\nResults saved to: {self.output_csv}")
        else:
            print("\n=== Overall Relevancy Results ===")
            print(df.to_string(index=False, float_format="%.4f"))

    def plot_heatmap(self) -> None:
        index = [os.path.basename(u) or u for u in self.urls]
        df_pq = pd.DataFrame(
            data=self.per_pdf_query_scores,
            index=index,
            columns=self.queries
        )
        print("Plotting heatmap...")
        plt.figure(figsize=(10, max(4, len(df_pq) * 0.3)))
        im = plt.imshow(df_pq.values, aspect='auto')
        plt.colorbar(im, label='Relevancy Score')
        plt.xticks(
            ticks=np.arange(len(self.queries)),
            labels=self.queries,
            rotation=45,
            ha='right'
        )
        plt.yticks(
            ticks=np.arange(len(df_pq.index)),
            labels=df_pq.index
        )
        plt.title('Relevancy Scores per PDF per Query')
        plt.tight_layout()
        plt.show()

    def run(self) -> None:
        # 1) Load URLs
        self.load_urls()
        # 2) Load queries
        print(f"Loading queries from: {self.queries_file}")
        self.queries = self.load_queries(self.queries_file)
        if not self.queries:
            print("Error: No queries to process.", file=sys.stderr)
            sys.exit(1)

        # 3) Init model and embed queries
        self.initialize_model()

        # 4) Process each PDF
        for url in self.urls:
            self.process_pdf(url)

        # 5) Save or print results
        self.save_results()

        # 6) Plot if enabled
        if self.enable_plot:
            self.plot_heatmap()


if __name__ == '__main__':
    # Example usage
    """
    scraper = RelevancyIndex(
        input_file="Pipeline/Sources/scraping/existing_pdf_links.txt", (or can be a .csv)
        queries_file="queries2.txt",
        output_csv="/results_queries2.csv",
        model_name="all-MiniLM-L6-v2",
        num_chunks=5,
        csv_url_column=None,  # or name of column in CSV
        enable_plot=True      # set False to skip plotting
    )
    scraper.run()
    """