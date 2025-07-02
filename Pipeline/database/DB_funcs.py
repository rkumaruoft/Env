import sqlite3
import json
from datetime import datetime


class ClimateDB:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.create_table_if_not_exists()

    def create_table_if_not_exists(self):
        """Check if 'documents' table exists and create it if not."""
        self.cursor.execute("""
        SELECT name FROM sqlite_master WHERE type='table' AND name='documents';
        """)
        if self.cursor.fetchone():
            print("ℹ️ Table 'documents' already exists.")
            return

        self.cursor.execute("""
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            type TEXT,
            authors TEXT,
            date TEXT,
            doi TEXT,
            publishing_organization TEXT,
            doc_name TEXT,
            relevancy_score REAL CHECK(relevancy_score >= 0 AND relevancy_score <= 1)
        )
        """)
        self.conn.commit()
        print("Table 'documents' created.")

    @staticmethod
    def normalize_date(date_str):
        """Convert date strings to ISO 8601 format if possible."""
        if not date_str:
            return None

        formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%B %Y", "%b %Y", "%Y"]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.date().isoformat()
            except ValueError:
                continue
        return date_str

    def insert_document(self, doc: dict) -> int:
        """Insert a single document into the database."""
        try:
            title = doc.get("title", "")
            if not isinstance(title, str) or not title.strip():
                print(title)
                print("Insert Failed: Missing or empty 'title'.")
                return -1

            doc_type = doc.get("type", "")
            if not isinstance(doc_type, str):
                doc_type = str(doc_type)

            authors = doc.get("authors", "")
            if isinstance(authors, list):
                authors = ", ".join(str(author) for author in authors)
            elif not isinstance(authors, str):
                authors = "NONE"

            date = self.normalize_date(doc.get("date", ""))
            doi = doc.get("doi") or doc.get("doi_link") or "NONE"
            publishing_org = doc.get("publishing_organization", "NONE")
            if not isinstance(publishing_org, str):
                publishing_org = str(publishing_org)

            doc_name = doc.get("doc_name", "")
            relevancy_score = doc.get("relevancy_score", 0.0)
            try:
                relevancy_score = float(relevancy_score)
            except ValueError:
                relevancy_score = 0.0

            self.cursor.execute("""
                INSERT INTO documents (title, type, authors, date, doi, publishing_organization, doc_name, relevancy_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (title.strip(), doc_type, authors, date, doi, publishing_org, doc_name, relevancy_score))
            self.conn.commit()
            return 0

        except Exception as e:
            print(f"Failed to insert document: {e}")
            return -1

    def title_exists(self, title: str) -> bool:
        """Check if a document with the given title already exists (case-insensitive)."""
        if not title or not isinstance(title, str):
            return False

        self.cursor.execute(
            "SELECT 1 FROM documents WHERE LOWER(title) = ? LIMIT 1",
            (title.strip().lower(),)
        )
        return self.cursor.fetchone() is not None

    def insert_from_json(self, json_path):
        """Clear the table and insert fresh data from a JSON file."""
        self.cursor.execute("DELETE FROM documents")
        self.conn.commit()
        print("Cleared existing records in 'documents' table.")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        inserted = 0
        for doc in data:
            if self.insert_document(doc) == 0:
                inserted += 1

        print(f"Inserted {inserted} documents from {json_path}")

    def get_all_titles(self):
        """Return a list of all document titles in the database."""
        self.cursor.execute("SELECT title FROM documents")
        rows = self.cursor.fetchall()
        return [row[0] for row in rows]

    def get_all_publishers(self) -> list:
        """Retrieve a list of all unique publishing organizations in lowercase."""
        self.cursor.execute("""
            SELECT DISTINCT LOWER(TRIM(publishing_organization))
            FROM documents
            WHERE publishing_organization IS NOT NULL AND TRIM(publishing_organization) != ''
        """)
        rows = self.cursor.fetchall()
        return [row[0] for row in rows if row[0]]

    def get_all_dois(self) -> list:
        """Retrieve a list of all unique DOI entries in lowercase."""
        self.cursor.execute("""
            SELECT DISTINCT LOWER(TRIM(doi))
            FROM documents
            WHERE doi IS NOT NULL AND TRIM(doi) != ''
        """)
        rows = self.cursor.fetchall()
        return [row[0] for row in rows if row[0]]

    def get_jsonl_object(self):
        """Return document data (excluding full text) as a list of JSON-style dicts."""
        self.cursor.execute("""
            SELECT title, type, authors, date, doi, publishing_organization, relevancy_score FROM documents
        """)
        rows = self.cursor.fetchall()

        jsonl_data = []

        for row in rows:
            title, doc_type, authors, date, doi, org, score = row

            if not title:
                continue

            record = {
                "title": title.strip(),
                "type": doc_type.strip() if doc_type else None,
                "authors": authors.strip() if authors else None,
                "date": date.strip() if date else None,
                "doi": doi.strip() if doi else None,
                "publishing_organization": org.strip() if org else None,
                "relevancy_score": score
            }

            jsonl_data.append(record)

        return jsonl_data

    def close(self):
        """Close the database connection."""
        self.conn.close()
        print("Database connection closed.")
