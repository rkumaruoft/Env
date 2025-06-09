import os

from Pipeline.google_drive.drive_connection import GoogleDriveHandler
from Pipeline.database.DB_funcs import ClimateDB
from Pipeline.google_drive.Gemeni_API import GeminiMetadataExtractor
import asyncio

if __name__ == "__main__":
    # google drive folder ID for PDFs_10_24
    folder_id = '1l70DlWzlHDsRrAJmoEQULhwCH22kDQ98'
    # drive object connected to google drive
    drive = GoogleDriveHandler("google_drive/chatbot-drive-pipe-service.json")
    gemini = GeminiMetadataExtractor("google_drive/gemini_api_key.txt")
    db_conn = ClimateDB("database/climate_docs.db")

    gemini.process_directory(directory='../MySQlDB/extracted_text')

    db_conn.insert_from_json(json_path="db_output.json")

    db_conn.close()

    # Start the APIs here to get new / updated pdfs
