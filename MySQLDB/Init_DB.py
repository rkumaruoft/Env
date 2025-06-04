import sqlite3
import json
import os


def create_connection(db_file):
    conn = sqlite3.connect(db_file)
    return conn


def create_table(conn):
    """Check if 'documents' table exists and create if it doesn't."""
    cursor = conn.cursor()

    # Check for table existence
    cursor.execute("""
    SELECT name FROM sqlite_master WHERE type='table' AND name='documents';
    """)
    table_exists = cursor.fetchone()

    if table_exists:
        print("Table 'documents' already exists. Skipping creation.")
    else:
        cursor.execute("""
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            type TEXT,
            authors TEXT,
            date TEXT,
            doi TEXT,
            publishing_organization TEXT
        )
        """)
        conn.commit()
        print("Table 'documents' created.")


def insert_document(conn, doc):
    cursor = conn.cursor()

    title = doc.get("title", "")
    doc_type = doc.get("type", "")
    authors = doc.get("authors", "")
    if isinstance(authors, list):
        authors = ", ".join(authors)
    date = doc.get("date", "")
    doi = doc.get("doi") or doc.get("doi_link") or "NONE"
    publishing_org = doc.get("publishing_organization", "NONE")

    cursor.execute("""
        INSERT INTO documents (title, type, authors, date, doi, publishing_organization)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (title, doc_type, authors, date, doi, publishing_org))
    conn.commit()


def load_json(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    json_path = "db_output.json"
    db_path = "climate_docs.db"

    data = load_json(json_path)
    conn = create_connection(db_path)
    create_table(conn)

    for doc in data:
        insert_document(conn, doc)

    conn.close()
    print(f"Inserted {len(data)} documents into {db_path}")
