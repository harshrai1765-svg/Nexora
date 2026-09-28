import os
import json

from backend.auth import hash_password
from backend.database import Base, engine, SessionLocal
from backend.models import User, Case, Document, DocumentVersion, AuditLog


ORIGINAL_HASH = "c8f3653d0e0ecb9fc2a4c5f8c87b78971ce8e67945e8071381fd6b5dd3bee66d"
CURRENT_HASH = "9f7c0a42663fb6661f0c2479530e80664793b5661c877496ce3c49bc447dcfad"

ORIGINAL_TEXT = """FIRST INFORMATION REPORT\nCase Number: NXR-2026-001\nDate of Report: 26 September 2026\nIncident Date: 26 September 2026\nReporting Officer: Inspector Demo Officer\nThis is a synthetic demonstration FIR for the Nexora prototype."""

CURRENT_TEXT = """FIRST INFORMATION REPORT\nCase Number: NXR-2026-001\nDate of Report: 27 September 2026\nIncident Date: 27 September 2026\nReporting Officer: Inspector Demo Officer\nThis is a synthetic demonstration FIR for the Nexora prototype."""


def seed_demo_data():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        password = os.getenv("NEXORA_ADMIN_PASSWORD")

        user = db.query(User).filter(User.username == "Harsh").first()
        if not user and password:
            user = User(
                username="Harsh",
                password_hash=hash_password(password),
                role="admin"
            )
            db.add(user)
            db.flush()

        case = db.query(Case).filter(Case.case_number == "NXR-2026-001").first()
        if not case:
            case = Case(
                case_number="NXR-2026-001",
                title="Sample Investigation Case",
                description="Synthetic legal investigation case for the Nexora prototype."
            )
            db.add(case)
            db.flush()

        document = (
            db.query(Document)
            .filter(Document.case_id == case.id)
            .filter(Document.filename == "Nexora_Sample_FIR_NXR-2026-001.pdf")
            .first()
        )

        if not document:
            document = Document(
                case_id=case.id,
                filename="Nexora_Sample_FIR_NXR-2026-001.pdf",
                document_type="FIR",
                current_version=2,
                current_hash=CURRENT_HASH
            )
            db.add(document)
            db.flush()

            v1 = DocumentVersion(
                document_id=document.id,
                version_number=1,
                filename="Nexora_Sample_FIR_NXR-2026-001.pdf",
                file_path=None,
                file_hash=ORIGINAL_HASH,
                ocr_text=ORIGINAL_TEXT,
                metadata_json=json.dumps({
                    "case_number": "NXR-2026-001",
                    "date": "26 September 2026",
                    "officer": "Inspector Demo Officer"
                })
            )

            v2 = DocumentVersion(
                document_id=document.id,
                version_number=2,
                filename="Nexora_Sample_FIR_NXR-2026-001_V2_MODIFIED.pdf",
                file_path=None,
                file_hash=CURRENT_HASH,
                ocr_text=CURRENT_TEXT,
                metadata_json=json.dumps({
                    "case_number": "NXR-2026-001",
                    "date": "27 September 2026",
                    "officer": "Inspector Demo Officer"
                })
            )

            db.add_all([v1, v2])
            db.flush()

            if user:
                db.add(AuditLog(
                    user_id=user.id,
                    document_id=document.id,
                    action="INTEGRITY_CHECK",
                    details="Compared version 1 with version 2. Integrity status: MODIFIED. Changes detected: 2."
                ))

        elif user:
            existing_audit = (
                db.query(AuditLog)
                .filter(AuditLog.document_id == document.id)
                .filter(AuditLog.action == "INTEGRITY_CHECK")
                .first()
            )
            if not existing_audit:
                db.add(AuditLog(
                    user_id=user.id,
                    document_id=document.id,
                    action="INTEGRITY_CHECK",
                    details="Compared version 1 with version 2. Integrity status: MODIFIED. Changes detected: 2."
                ))

        db.commit()

    finally:
        db.close()
