#!/usr/bin/env python3
"""
relevancy_index_nlp_with_plots.py

For each PDF link listed in a hard-coded text file, download the PDF,
split its text into a fixed number of chunks (5 by default),
embed those chunks with a SentenceTransformer model along with a set of natural-language
queries, compute a "relevancy index" per PDF (average of the maximum cosine similarity
per query), and then plot a heatmap of each PDF’s relevancy score for each query.

Dependencies:
    pip install PyPDF2 sentence-transformers scikit-learn pandas torch matplotlib requests

Usage:
    1) Edit the HARD-CODED SETTINGS at the top:
         • pdf_urls_file → path to a .txt file with one PDF URL per line.
         • queries_file  → path to a .txt file with one query per line.
         • output_csv    → path to save overall scores CSV (or None to only print).
         • model_name    → SentenceTransformer model name.
         • num_chunks    → number of equal-sized chunks per PDF.
    2) Run: python relevancy_index_nlp_with_plots.py
"""

import os
import sys
import io
import requests
from typing import List
import PyPDF2
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# ─────────────────────────────────────────────────────────────────────────────
#  HARD-CODED SETTINGS: edit these paths and parameters before running
# ─────────────────────────────────────────────────────────────────────────────
pdf_urls_file = "/scraping/existing_pdf_links.txt"    # one PDF URL per line
queries_file  = "/scraping/relevancy_index/queries2.txt"     # one query per line
output_csv    = "/scraping/relevancy_index/results_queries2.csv"  # or None to only print results
model_name    = "all-MiniLM-L6-v2"
num_chunks    = 5
# ─────────────────────────────────────────────────────────────────────────────


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """
    Extract text from PDF bytes via PyPDF2.
    Returns concatenated pages or empty string on error.
    """
    text_chunks: List[str] = []
    try:
        with io.BytesIO(pdf_bytes) as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_chunks.append(page_text)
    except Exception as e:
        print(f"Warning: could not parse PDF bytes: {e}", file=sys.stderr)
        return ""
    return "\n".join(text_chunks)


def chunk_text_to_n(text: str, n: int) -> List[str]:
    """
    Split `text` into `n` chunks of (almost) equal word count.
    """
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


def load_queries(path: str) -> List[str]:
    """
    Read queries from a file, one non-blank line per query.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Queries file not found: {path}")
    queries: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            q = line.strip()
            if q:
                queries.append(q)
    return queries


def main():
    # 1) Verify PDF URLs file and queries file exist
    if not os.path.isfile(pdf_urls_file):
        print(f"Error: PDF URLs file not found: {pdf_urls_file}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(queries_file):
        print(f"Error: Queries file not found: {queries_file}", file=sys.stderr)
        sys.exit(1)

    # 2) Load PDF URLs
    with open(pdf_urls_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]
    if not urls:
        print(f"Error: No URLs found in: {pdf_urls_file}", file=sys.stderr)
        sys.exit(1)

    # 3) Load and encode queries
    print(f"Loading queries from: {queries_file}")
    queries = load_queries(queries_file)
    if not queries:
        print("Error: No queries to process.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading model '{model_name}'…")
    model = SentenceTransformer(model_name)
    print("Embedding queries…")
    query_embeds = model.encode(queries, convert_to_numpy=True, show_progress_bar=False)

    # 4) Process each PDF URL
    results = []
    per_pdf_query_scores = []
    for url in urls:
        print(f"Downloading {url}…", end="", flush=True)
        try:
            resp = requests.get(url)
            resp.raise_for_status()
            pdf_bytes = resp.content
        except Exception as e:
            print(f" failed to download: {e}", file=sys.stderr)
            continue

        text = extract_text_from_pdf_bytes(pdf_bytes)
        chunks = chunk_text_to_n(text, num_chunks)
        if not chunks:
            scores = np.zeros(len(queries))
            relevancy = 0.0
        else:
            chunk_embeds = model.encode(chunks, convert_to_numpy=True, show_progress_bar=False)
            sims = cosine_similarity(query_embeds, chunk_embeds)
            scores = sims.max(axis=1)
            relevancy = float(np.mean(scores))

        per_pdf_query_scores.append(scores)
        results.append((url, relevancy))
        print(f" relevancy = {relevancy:.4f}")

    # 5) Build and save/print overall relevancy DataFrame
    df = pd.DataFrame(results, columns=['pdf_url','relevancy_index'])
    df = df.sort_values('relevancy_index', ascending=False).reset_index(drop=True)
    if output_csv:
        df.to_csv(output_csv, index=False)
        print(f"\nResults saved to: {output_csv}")
    else:
        print("\n=== Overall Relevancy Results (sorted) ===")
        print(df.to_string(index=False, float_format='%.4f'))

    # 6) Plot heatmap of per-query relevancy
    print("\nPlotting heatmap…")
    df_per_query = pd.DataFrame(
        data=per_pdf_query_scores,
        index=[os.path.basename(u) or u for u in urls],
        columns=queries
    )
    plt.figure(figsize=(10, max(4, len(df_per_query)*0.3)))
    im = plt.imshow(df_per_query.values, aspect='auto')
    plt.colorbar(im, label='Relevancy Score')
    plt.xticks(
        ticks=np.arange(len(queries)),
        labels=queries,
        rotation=45,
        ha='right'
    )
    plt.yticks(
        ticks=np.arange(len(df_per_query.index)),
        labels=df_per_query.index
    )
    plt.title('Relevancy Scores per PDF per Query')
    plt.tight_layout()
    plt.show()

if __name__ == '__main__':
    main()