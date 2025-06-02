from drive_connection import *
import fitz


def save_local(pdf_list):
    text_dir = 'extracted_text'
    os.makedirs(text_dir, exist_ok=True)

    for pdf in pdf_list:
        name = pdf['name'].replace('/', '_').replace('\\', '_').replace('.pdf', '')
        file_path = os.path.join(text_dir, f"{name}.txt")

        # Extract text from in-memory BytesIO
        try:
            pdf['content'].seek(0)
            doc = fitz.open(stream=pdf['content'].read(), filetype="pdf")

            full_text = ""
            for page in doc:
                full_text += page.get_text()

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(full_text)

            print(f"📝 Extracted text saved: {file_path}")

        except Exception as e:
            print(f"❌ Failed to extract text from {pdf['name']}: {e}")

if __name__ == '__main__':
    folder_id = '1l70DlWzlHDsRrAJmoEQULhwCH22kDQ98'
    service = get_drive_service()
    pdf_list, skipped = download_pdfs(folder_id, service)
    print(f"\n✅ Downloaded {len(pdf_list)} PDFs recursively from folder {folder_id}.")
    print(f"❌ Skipped {len(skipped)} files due to access issues.")

    save_local(pdf_list)
