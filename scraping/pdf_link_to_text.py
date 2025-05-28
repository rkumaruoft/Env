url = "https://www.toronto.ca/wp-content/uploads/2025/05/960f-Green-Will-Initiative-2025-Collaboration-Series-Session-1-Resource-Sheet.pdf"

from pypdf import PdfReader
import requests
import io

response = requests.get(url)
pdf_file = io.BytesIO(response.content)
reader = PdfReader(pdf_file)

text = ""

for page in reader.pages:
    text += page.extract_text() + "\n"

print(text)