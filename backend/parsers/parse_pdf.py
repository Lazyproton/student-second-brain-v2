# Extracts text content from PDF files using PyMuPDF (imported as fitz)

import re
import fitz  # PyMuPDF


# Accepts a local file path to a PDF, opens it with PyMuPDF, extracts text from
# every page, collapses excessive whitespace, and returns the full text along
# with the total page count and word count.
def extract_pdf_text(file_path: str) -> dict:
    """
    Extracts all readable text from a local PDF file.

    Args:
        file_path (str): Absolute or relative path to the PDF file.

    Returns:
        dict with keys:
            - "text"       (str): Full extracted and cleaned text.
            - "page_count" (int): Total number of pages in the PDF.
            - "word_count" (int): Number of words in the extracted text.
        On error:
            - "text"       (str): ""
            - "page_count" (int): 0
            - "error"      (str): Error message.
    """
    try:
        doc = fitz.open(file_path)
        page_count = len(doc)

        pages_text = []
        for page_num in range(page_count):
            page = doc[page_num]
            pages_text.append(page.get_text())

        doc.close()

        # Join pages with a newline separator, then clean up whitespace
        raw_text = "\n".join(pages_text)
        # Collapse 3+ consecutive newlines to 2 (preserve paragraph breaks)
        cleaned = re.sub(r"\n{3,}", "\n\n", raw_text)
        # Collapse multiple spaces on the same line
        cleaned = re.sub(r" {2,}", " ", cleaned).strip()

        return {
            "text":       cleaned,
            "page_count": page_count,
            "word_count": len(cleaned.split()),
        }

    except FileNotFoundError:
        return {"text": "", "page_count": 0, "error": f"File not found: {file_path}"}
    except Exception as e:
        return {"text": "", "page_count": 0, "error": str(e)}
