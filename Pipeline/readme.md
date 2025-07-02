# 🌎 MLCC Pipeline

A **modular pipeline** for discovering, collecting, and analyzing **public climate-related documents**, especially from municipal and institutional sources (e.g., `toronto.ca`). This project is designed for **retrieval-augmented generation (RAG)** workflows and broader environmental data analysis.

---

## 🚧 Project Status

This pipeline is currently **under active development**.

### ✅ Fully Working Modules
- **`GoogleDriveHandler`** – Uploads and organizes PDFs in Google Drive
- **`GeminiMetadataExtractor`** – Uses Gemini Pro to extract structured metadata from PDF text
- **`ClimateDB`** – Stores and queries document metadata in a local SQLite database
- **`RelevancyIndex`** – Prototype for chunking, embedding, and scoring documents
- 
### ⚙️ In Progress / Prototype Stage
- **`SitemapScraper`** – Discovers PDFs from sitemap.xml files (working; integration pending)
- **`ClimateDocsUpdater`** – Module to update the existing pdfs
- **`API Integration`**

---

## 🎯 Project Goals

- 🔍 Discover and download public PDFs on climate topics
- 🤖 Generate structured metadata using LLMs (Gemini)
- 🗂 Store results in a searchable local database
- 🔬 Score documents based on semantic relevance to queries
- 💬 Serve document chunks in a future chatbot or reporting interface

---

## 🧱 Pipeline Architecture

### 1. `GoogleDriveHandler` ✅
- Uploads PDFs to organized Google Drive folders
- Adds metadata tagging for easy retrieval

### 2. `GeminiMetadataExtractor` ✅
- Extracts fields like:
  - Title
  - Topics
  - Summary
  - Document type etc.
- Input: raw PDF text
- Output: structured metadata dictionary

### 3. `ClimateDB` ✅
- Lightweight SQLite database
- Provides insert, update, and search methods
- Supports export to JSON or CSV

### 4. `SitemapScraper` ⚙️
- Recursively parses `sitemap.xml` files
- Filters `.pdf` URLs using keyword matching
- Designed to plug directly into the pipeline

### 5. `RelevancyIndex` ⚙️
- Splits documents into semantic chunks
- Embeds using `SentenceTransformer`
- Scores chunks by cosine similarity to queries

### 7. `APIHandler` 🧪 (Experimental)
- Located in `Sources/API_class.py` and `API_single_class.py`
- Intended to interact with external APIs (e.g., ScienceDirect, DOI resolvers)
- Currently disjointed and lacks integration with the main pipeline
- Needs consolidation and redesign for robust batch/streamed metadata ingestion.

---

## 📁 Project Structure

```
.
├── main.py                       # Pipeline entry point (integration hub)
├── readme.md                    # This file
├── requirements.txt             # All Python dependencies
├── db_output.json               # (Optional) Output logs from DB
├── structure.txt                # Tree view of file layout

├── database/
│   ├── climate_docs.db          # SQLite database
│   ├── DB_funcs.py              # ClimateDB class and helpers
│   ├── nomic.py                 # (Optional) Nomic integration
│   └── nomic_upload.jsonl       # Formatted upload data

├── google_drive/
│   ├── drive_connection.py      # GDrive upload and folder logic
│   ├── Gemeni_API.py            # GeminiMetadataExtractor class
│   ├── gemini_api_key.txt       # Gemini API key
│   └── chatbot-drive-pipe-service.json # GCP credentials

├── relevancy_index/
│   ├── RelevancyIndex.py        # Prototype class (consider clean up)
│   ├── Relvency_Index.py        # Main class for semantic search
│   └── queries2.txt             # Sample queries

├── Sources/
│   ├── API_class.py             # PDF API handler
│   ├── API_single_class.py      # One-off API runner
│   ├── link_scraper.py          # Legacy scraper
│   ├── sitemap_scraper.py       # SitemapScraper class
│   ├── update_existing_pdfs.py  # ClimateDocsUpdater logic
│   ├── API_PDF_links.txt        # Discovered links via APIs
│   ├── Science_direct_key       # (Consider renaming/moving)
│
│   └── scraping/
│       ├── existing_pdf_links.txt # Discovered PDF URLs
│       ├── doi_list.txt           # DOIs for follow-up
│       └── link_to_text.py        # Text extraction tool
```

---

## 🔧 Setup Instructions

### Prerequisites
- Python 3.10+
- Google Cloud service account with Drive API enabled
- Gemini API key from Google AI Studio
- SQLite for `ClimateDB`

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 🔒 Authentication Setup

- Place your Gemini API key in:
  ```
  google_drive/gemini_api_key.txt
  ```
- Google Drive credentials:
  ```
  google_drive/chatbot-drive-pipe-service.json
  ```

---

## 📌 Notes

- Modular components can be run independently for testing
- Integration via `main.py` is currently in development
- Consider cleaning duplicate scripts (e.g., `RelvencyIndex.py`)