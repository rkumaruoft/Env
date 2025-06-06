from Key_words import read_queries, extract_keywords_tfidf
import os
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer

def read_text_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def cosine_similarity(vec1, vec2):
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

def normalize_score(score):
    return (score + 1) / 2  # convert cosine from [-1,1] to [0,1]

def score_text_against_keywords(text, keywords, model):
    text_emb = model.encode(text)
    total_score = 0
    for keyword in keywords:
        kw_emb = model.encode(keyword)
        sim = cosine_similarity(text_emb, kw_emb)
        total_score += normalize_score(sim)
    return total_score

def aggregate_scores_per_file(txt_folder, queries, keywords_per_query):
    model = SentenceTransformer('all-MiniLM-L6-v2')
    file_scores = {}

    for filename in os.listdir(txt_folder):
        if not filename.endswith('.txt'):
            continue

        filepath = os.path.join(txt_folder, filename)
        text = read_text_file(filepath)

        total_score = 0
        for keywords in keywords_per_query:
            total_score += score_text_against_keywords(text, keywords, model)

        file_scores[filename] = total_score

    return file_scores

if __name__ == "__main__":
    queries = read_queries("Queries")
    keywords_per_query = extract_keywords_tfidf(queries, top_k=3)

    folder = "txtfiles"
    file_scores = aggregate_scores_per_file(folder, queries, keywords_per_query)

    for filename, score in sorted(file_scores.items(), key=lambda x: -x[1]):
        print(f"{filename} | Final Score: {score:.2f}")

