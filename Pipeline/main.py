from Pipeline.google_drive.drive_connection import GoogleDriveHandler
from Pipeline.database.DB_funcs import ClimateDB
from Pipeline.google_drive.Gemeni_API import GeminiMetadataExtractor
import asyncio
from Pipeline.Sources.link_scraper import run_link_scraper

if __name__ == "__main__":
    # google drive folder ID for PDFs_10_24
    folder_id = '1l70DlWzlHDsRrAJmoEQULhwCH22kDQ98'
    # drive object connected to google drive
    drive = GoogleDriveHandler("google_drive/chatbot-drive-pipe-service.json")
    gemini = GeminiMetadataExtractor("google_drive/gemini_api_key.txt")
    db_conn = ClimateDB("database/climate_docs.db")

    # Start the scrapper here and get the new/updated pdfs

    # Start the APIs here to get new / updated pdfs