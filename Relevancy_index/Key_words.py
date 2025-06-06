from sklearn.feature_extraction.text import TfidfVectorizer

def read_queries(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        queries = [line.strip() for line in f if line.strip()]
    return queries

def extract_keywords_tfidf(queries, top_k=3):
    vectorizer = TfidfVectorizer(stop_words='english')
    X = vectorizer.fit_transform(queries)
    feature_names = vectorizer.get_feature_names_out()

    keywords_list = []
    for row in X:
        # Get tf-idf scores for this query
        row_data = row.toarray().flatten()
        # Get indices of top k tf-idf scores
        top_indices = row_data.argsort()[-top_k:][::-1]
        keywords = [feature_names[i] for i in top_indices]
        keywords_list.append(keywords)
    return keywords_list

if __name__ == "__main__":
    queries = read_queries("Queries")
    keywords_per_query = extract_keywords_tfidf(queries, top_k=3)
    for q, kws in zip(queries, keywords_per_query):
        print(f"Query: {q}\nKeywords: {kws}\n")