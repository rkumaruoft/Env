from Pipeline.google_drive.drive_connection import GoogleDriveHandler
from Pipeline.database.DB_funcs import ClimateDB
from Pipeline.google_drive.Gemeni_API import GeminiMetadataExtractor
from Pipeline.relevancy_index.Relvency_Index import RelevancyIndex
from Pipeline.Sources.sitemap_scraper import SitemapScraper

def get_lines_from_txt(file_path: str) -> list[str]:
    """
    Reads all lines from a text file and returns them as a list of strings,
    with trailing newline characters removed.

    Args:
        file_path (str): Path to the text file.

    Returns:
        list[str]: List of lines in the file.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


if __name__ == "__main__":
    # google drive folder ID for PDFs_10_24
    folder_id = '1l70DlWzlHDsRrAJmoEQULhwCH22kDQ98'
    # drive object connected to google drive
    drive = GoogleDriveHandler("google_drive/chatbot-drive-pipe-service.json")
    gemini = GeminiMetadataExtractor("google_drive/gemini_api_key.txt")
    db_conn = ClimateDB("database/climate_docs.db")

    queries = get_lines_from_txt(file_path="relevancy_index/queries2.txt")
    relevancy = RelevancyIndex(queries, model_name="all-MiniLM-L6-v2", num_chunks=5)

    db_conn.insert_from_json(json_path="db_output.json")

    # Start the APIs here to get new / updated pdfs

    db_conn.close()
