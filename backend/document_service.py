from pathlib import Path
import hashlib


BASE_DIR = Path(__file__).resolve().parent.parent

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def calculate_sha256(file_path: Path) -> str:
    """
    Calculate the SHA-256 hash of a file.
    """

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:
        while chunk := file.read(1024 * 1024):
            sha256.update(chunk)

    return sha256.hexdigest()


def save_uploaded_file(file_content: bytes, filename: str) -> Path:
    """
    Save an uploaded document into the Nexora uploads directory.
    """

    safe_filename = Path(filename).name

    file_path = UPLOAD_DIR / safe_filename

    with open(file_path, "wb") as file:
        file.write(file_content)

    return file_path