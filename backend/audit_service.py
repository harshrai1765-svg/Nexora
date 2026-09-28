from sqlalchemy.orm import Session

from backend.models import AuditLog, User


def create_audit_log(
    db: Session,
    user: User,
    action: str,
    document_id: int | None = None,
    details: str | None = None
):
    """
    Create an audit trail entry for a Nexora action.
    """

    audit = AuditLog(
        user_id=user.id,
        document_id=document_id,
        action=action,
        details=details
    )

    db.add(audit)
    db.commit()
    db.refresh(audit)

    return audit