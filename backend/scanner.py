from pathlib import Path
import re

from pypdf import PdfReader


def extract_pdf_text(file_path: Path) -> str:
    """Extract selectable text from a PDF."""

    reader = PdfReader(str(file_path))

    pages = []

    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)

    return "\n".join(pages).strip()


def classify_document(text: str, filename: str) -> str:
    """Classify a legal document using simple keyword evidence."""

    content = f"{filename} {text}".lower()

    if "first information report" in content or "fir" in content:
        return "FIR"

    if "charge sheet" in content or "chargesheet" in content:
        return "Charge Sheet"

    if "witness statement" in content or "statement of witness" in content:
        return "Witness Statement"

    if "forensic report" in content or "forensic analysis" in content:
        return "Forensic Report"

    if "court order" in content or "court judgment" in content:
        return "Court Document"

    if "legal notice" in content:
        return "Legal Notice"

    if "investigation report" in content:
        return "Investigation Report"

    return "Legal Document"


def extract_metadata(text: str) -> dict:
    """Extract useful metadata from the document text."""

    metadata = {}

    case_match = re.search(
        r"Case\s*(?:Number|No\.?)\s*[:\-]?\s*([A-Z0-9\-\/]+)",
        text,
        re.IGNORECASE
    )

    if case_match:
        metadata["case_number"] = case_match.group(1)

    date_match = re.search(
        r"(?:Date of Report|Date)\s*[:\-]?\s*([0-9]{1,2}\s+\w+\s+[0-9]{4}|[0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        text,
        re.IGNORECASE
    )

    if date_match:
        metadata["date"] = date_match.group(1)

    officer_match = re.search(
        r"(?:Reporting Officer|Investigating Officer|Officer)\s*[:\-]?\s*(.+)",
        text,
        re.IGNORECASE
    )

    if officer_match:
        metadata["officer"] = officer_match.group(1).strip()

    return metadata


def scan_document(file_path: Path, filename: str) -> dict:
    """Run the Nexora document intelligence pipeline."""

    text = extract_pdf_text(file_path)

    document_type = classify_document(text, filename)

    metadata = extract_metadata(text)

    return {
        "document_type": document_type,
        "metadata": metadata,
        "text_length": len(text),
        "text": text
    }