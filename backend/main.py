from pathlib import Path
import json

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware 
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.auth import create_access_token, hash_password, verify_password
from backend.database import get_db
from backend.models import User, Case, Document, DocumentVersion, AuditLog
from backend.dependencies import get_current_user
from backend.document_service import calculate_sha256, save_uploaded_file
from backend.scanner import scan_document

from backend.comparison import compare_versions

from backend.audit_service import create_audit_log 

security = HTTPBearer()


app = FastAPI(
    title="Nexora",
    description="Secure Digital Document Management System",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "investigator"


class LoginRequest(BaseModel):
    username: str
    password: str


class CaseCreateRequest(BaseModel):
    case_number: str
    title: str
    description: str | None = None


@app.get("/")
def root():
    return FileResponse(
        Path(__file__).resolve().parent.parent / "frontend" / "index.html"
    )


@app.post("/register")
def register_user(
    user_data: RegisterRequest,
    db: Session = Depends(get_db)
):
    existing_user = (
        db.query(User)
        .filter(User.username == user_data.username)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    new_user = User(
        username=user_data.username,
        password_hash=hash_password(user_data.password),
        role=user_data.role
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "User registered successfully",
        "username": new_user.username,
        "role": new_user.role
    }


@app.post("/login")
def login_user(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    user = (
        db.query(User)
        .filter(User.username == login_data.username)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    if not verify_password(
        login_data.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    access_token = create_access_token(
        {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role
        }
    )

    return {
        "message": "Login successful",
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role
    }


@app.get("/me")
def get_my_profile(
    current_user: User = Depends(get_current_user),
    credentials=Depends(security)
):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role
    }


@app.post("/cases")
def create_case(
    case_data: CaseCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existing_case = (
        db.query(Case)
        .filter(Case.case_number == case_data.case_number)
        .first()
    )

    if existing_case:
        raise HTTPException(
            status_code=400,
            detail="Case number already exists"
        )

    new_case = Case(
        case_number=case_data.case_number,
        title=case_data.title,
        description=case_data.description
    )

    db.add(new_case)
    db.commit()
    db.refresh(new_case)

    return {
        "message": "Case created successfully",
        "case_id": new_case.id,
        "case_number": new_case.case_number,
        "title": new_case.title,
        "created_by": current_user.username
    }


@app.get("/cases")
def list_cases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cases = (
        db.query(Case)
        .order_by(Case.created_at.desc())
        .all()
    )

    return {
        "total_cases": len(cases),
        "cases": [
            {
                "id": case.id,
                "case_number": case.case_number,
                "title": case.title,
                "description": case.description,
                "created_at": case.created_at
            }
            for case in cases
        ]
    }


@app.delete("/cases/{case_id}")
def delete_case(
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    case = (
        db.query(Case)
        .filter(Case.id == case_id)
        .first()
    )

    if not case:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    db.delete(case)
    db.commit()

    return {
        "message": "Case deleted successfully",
        "case_id": case_id,
        "deleted_by": current_user.username
    }


@app.post("/cases/{case_id}/documents")
async def upload_document(
    case_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    case = (
        db.query(Case)
        .filter(Case.id == case_id)
        .first()
    )

    if not case:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required"
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF documents are currently supported"
        )

    file_content = await file.read()

    if not file_content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty"
        )

    saved_path = save_uploaded_file(
        file_content,
        file.filename
    )

    file_hash = calculate_sha256(saved_path)

    new_document = Document(
        case_id=case.id,
        filename=file.filename,
        document_type="PDF",
        current_version=1,
        current_hash=file_hash
    )

    db.add(new_document)
    db.flush()

    scan_result = scan_document(
        saved_path,
        file.filename
    )

    first_version = DocumentVersion(
        document_id=new_document.id,
        version_number=1,
        filename=file.filename,
        file_path=str(saved_path),
        file_hash=file_hash,
        ocr_text=scan_result["text"],
        metadata_json=json.dumps(scan_result["metadata"])
    )

    db.add(first_version)
    db.commit()
    db.refresh(new_document)

    return {
        "message": "Document uploaded successfully",
        "document_id": new_document.id,
        "case_id": case.id,
        "filename": file.filename,
        "version": 1,
        "sha256": file_hash,
        "document_type": scan_result["document_type"],
        "metadata": scan_result["metadata"],
        "uploaded_by": current_user.username
    }


@app.post("/documents/{document_id}/versions")
async def upload_document_version(
    document_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required"
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF documents are currently supported"
        )

    file_content = await file.read()

    if not file_content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty"
        )

    next_version = document.current_version + 1

    saved_path = save_uploaded_file(
        file_content,
        f"document_{document.id}_v{next_version}.pdf"
    )

    new_hash = calculate_sha256(saved_path)

    if new_hash == document.current_hash:
        saved_path.unlink(missing_ok=True)

        raise HTTPException(
            status_code=400,
            detail="Uploaded document is identical to the current version"
        )

    scan_result = scan_document(
        saved_path,
        file.filename
    )

    new_version = DocumentVersion(
        document_id=document.id,
        version_number=next_version,
        filename=file.filename,
        file_path=str(saved_path),
        file_hash=new_hash,
        ocr_text=scan_result["text"],
        metadata_json=json.dumps(scan_result["metadata"])
    )

    document.current_version = next_version
    document.current_hash = new_hash

    db.add(new_version)
    db.commit()

    create_audit_log(
        db=db,
        user=current_user,
        action="VERSION_CREATED",
        document_id=document.id,
        details=(
            f"Document version {next_version} uploaded. "
            f"SHA-256: {new_hash}"
        )
    )

    return {
        "message": "New document version stored successfully",
        "document_id": document.id,
        "version": next_version,
        "filename": file.filename,
        "sha256": new_hash,
        "document_type": scan_result["document_type"],
        "metadata": scan_result["metadata"],
        "uploaded_by": current_user.username
    }


@app.get("/documents/{document_id}/scan")
def scan_uploaded_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    version = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == document.id,
            DocumentVersion.version_number == document.current_version
        )
        .first()
    )

    if not version:
        raise HTTPException(
            status_code=404,
            detail="Document version not found"
        )

    result = scan_document(
        Path(version.file_path),
        document.filename
    )

    return {
        "document_id": document.id,
        "filename": document.filename,
        "version": document.current_version,
        "sha256": document.current_hash,
        "document_type": result["document_type"],
        "metadata": result["metadata"],
        "text_length": result["text_length"],
        "extracted_text": result["text"],
        "scanner": "Nexora Document Intelligence"
    }

@app.get("/documents/{document_id}/compare")
def compare_document_versions(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    versions = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == document.id
        )
        .order_by(DocumentVersion.version_number.asc())
        .all()
    )

    if len(versions) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least two document versions are required for comparison"
        )

    original_version = versions[0]
    current_version = versions[-1]

    original_text = original_version.ocr_text or ""
    current_text = current_version.ocr_text or ""

    comparison = compare_versions(
        original_text,
        current_text
    )

    create_audit_log(
        db=db,
        user=current_user,
        action="INTEGRITY_CHECK",
        document_id=document.id,
        details=(
            f"Compared version {original_version.version_number} "
            f"with version {current_version.version_number}. "
            f"Integrity status: "
            f"{'MODIFIED' if comparison['changed'] else 'UNCHANGED'}. "
            f"Changes detected: {comparison['change_count']}."
        )
    )

    return {
        "document_id": document.id,
        "filename": document.filename,
        "original_version": original_version.version_number,
        "current_version": current_version.version_number,
        "original_sha256": original_version.file_hash,
        "current_sha256": current_version.file_hash,
        "integrity_status": (
            "MODIFIED"
            if comparison["changed"]
            else "UNCHANGED"
        ),
        "change_count": comparison["change_count"],
        "changes": comparison["changes"],
        "analyzed_by": current_user.username
    }

@app.get("/documents/{document_id}/audit")
def get_document_audit(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    logs = (
        db.query(AuditLog)
        .filter(AuditLog.document_id == document_id)
        .order_by(AuditLog.timestamp.desc())
        .all()
    )

    return {
        "document_id": document_id,
        "document_name": document.filename,
        "audit_count": len(logs),
        "audit_trail": [
            {
                "id": log.id,
                "action": log.action,
                "details": log.details,
                "performed_by": (
                    log.user.username
                    if log.user
                    else "Unknown"
                ),
                "timestamp": log.timestamp
            }
            for log in logs
        ]
    }

# =========================
# DASHBOARD STATS
# =========================

@app.get("/dashboard/stats")
def dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    total_cases = db.query(Case).count()
    total_documents = db.query(Document).count()

    integrity_checks = (
        db.query(AuditLog)
        .filter(AuditLog.action == "INTEGRITY_CHECK")
        .count()
    )

    modified_alerts = 0

    integrity_logs = (
        db.query(AuditLog)
        .filter(AuditLog.action == "INTEGRITY_CHECK")
        .all()
    )

    for log in integrity_logs:
        if log.details and "MODIFIED" in log.details:
            modified_alerts += 1

    return {
        "total_cases": total_cases,
        "total_documents": total_documents,
        "integrity_checks": integrity_checks,
        "alerts": modified_alerts
    }


# =========================
# CASE DOCUMENTS
# =========================

@app.get("/cases/{case_id}/documents")
def list_case_documents(
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    case = (
        db.query(Case)
        .filter(Case.id == case_id)
        .first()
    )

    if not case:
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    documents = (
        db.query(Document)
        .filter(Document.case_id == case_id)
        .order_by(Document.created_at.desc())
        .all()
    )

    return {
        "case_id": case_id,
        "document_count": len(documents),
        "documents": [
            {
                "id": document.id,
                "filename": document.filename,
                "document_type": document.document_type,
                "current_version": document.current_version,
                "current_hash": document.current_hash,
                "created_at": document.created_at
            }
            for document in documents
        ]
    }