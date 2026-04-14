from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.admin import AuditLogFilters, AuditLogItem, PaginatedAuditLogs


class AdminAuditService:
    @staticmethod
    def get_audit_logs(
        db: Session,
        *,
        page: int,
        size: int,
        filters: AuditLogFilters,
    ) -> PaginatedAuditLogs:
        query = db.query(AuditLog, User).outerjoin(User, User.id == AuditLog.actor_user_id)

        if filters.action:
            query = query.filter(AuditLog.action == filters.action)

        if filters.actor_user_id:
            query = query.filter(AuditLog.actor_user_id == filters.actor_user_id)

        if filters.entity_type:
            query = query.filter(AuditLog.entity_type == filters.entity_type)

        if filters.entity_id is not None:
            query = query.filter(AuditLog.entity_id == filters.entity_id)

        if filters.created_from is not None:
            query = query.filter(AuditLog.created_at >= filters.created_from)

        if filters.created_to is not None:
            query = query.filter(AuditLog.created_at <= filters.created_to)

        if (
            filters.created_from is not None
            and filters.created_to is not None
            and filters.created_to < filters.created_from
        ):
            raise HTTPException(
                status_code=400,
                detail="created_to must be greater than or equal to created_from",
            )

        total = query.with_entities(func.count(AuditLog.id)).scalar() or 0

        offset = max(0, (page - 1) * size)
        rows = (
            query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset(offset)
            .limit(size)
            .all()
        )

        items = [
            AuditLogItem(
                id=audit_log.id,
                actor_user_id=audit_log.actor_user_id,
                actor_name=actor.name if actor is not None else None,
                actor_email=actor.email if actor is not None else None,
                action=audit_log.action,
                entity_type=audit_log.entity_type,
                entity_id=audit_log.entity_id,
                meta_data=audit_log.meta_data,
                ip_address=audit_log.ip_address,
                created_at=audit_log.created_at,
            )
            for audit_log, actor in rows
        ]

        return PaginatedAuditLogs(items=items, total=total, page=page, size=size)
