import os
import logging
import aiofiles
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError

from app.models.license import License
from app.models.license_resubmission import LicenseResubmission
from app.models.user import User
from app.core.config import settings
from app.schemas.license import LicenseCreate
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024  # 1 MB chunks
UPLOAD_FILENAME_ENTROPY_LENGTH = 12
UPLOAD_FILENAME_MAX_ATTEMPTS = 5
MAGIC_SIGNATURES = {
    ".pdf": (b"%PDF-",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
}
EXTENSION_TO_MIME = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

class LicenseService:
    """Service for managing license verification workflow."""

    @staticmethod
    def _upload_root() -> Path:
        return settings.UPLOAD_ROOT

    @staticmethod
    def _is_unique_constraint_error(
        exc: IntegrityError,
        *,
        constraint_names: tuple[str, ...] = (),
        required_terms: tuple[str, ...] = (),
    ) -> bool:
        details = " ".join(
            [
                str(exc).lower(),
                str(getattr(exc, "orig", "")).lower(),
                str(getattr(exc, "statement", "")).lower(),
                str(getattr(exc, "params", "")).lower(),
            ]
        )
        has_duplicate_marker = any(
            marker in details
            for marker in (
                "duplicate",
                "duplicate entry",
                "duplicate key value",
                "unique constraint",
                "unique constraint failed",
            )
        )
        if not has_duplicate_marker:
            return False

        has_named_constraint = any(name.lower() in details for name in constraint_names)
        has_required_terms = bool(required_terms) and all(term.lower() in details for term in required_terms)
        if constraint_names and required_terms:
            return has_named_constraint or has_required_terms
        if constraint_names:
            return has_named_constraint
        if required_terms:
            return has_required_terms
        return False

    @staticmethod
    def _resolve_stored_document_path(document_path: str) -> Path:
        upload_root = LicenseService._upload_root()
        raw_path = Path(document_path)

        if raw_path.is_absolute():
            candidate = raw_path.resolve()
        else:
            relative_path = raw_path
            configured_upload_dir = Path(settings.UPLOAD_DIR)
            if not configured_upload_dir.is_absolute():
                try:
                    # Backward compatibility for legacy rows like "uploads/licenses/...".
                    relative_path = raw_path.relative_to(configured_upload_dir)
                except ValueError:
                    pass
            elif raw_path.parts and raw_path.parts[0] == configured_upload_dir.name:
                # Backward compatibility for legacy rows after switching UPLOAD_DIR
                # from relative ("uploads/...") to absolute ("/.../uploads").
                relative_path = Path(*raw_path.parts[1:])
            candidate = (upload_root / relative_path).resolve()

        try:
            candidate.relative_to(upload_root)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid document path") from exc
        return candidate

    @staticmethod
    def _validate_file(file: UploadFile) -> None:
        """
        Validate uploaded file.

        Args:
            file: Uploaded file to validate

        Raises:
            HTTPException: If file is invalid
        """
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        raw_filename = file.filename.strip()
        if not raw_filename:
            raise HTTPException(status_code=400, detail="Filename cannot be blank")

        # Reject path-like filenames to prevent traversal-style payloads.
        if Path(raw_filename).name != raw_filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        file_ext = Path(raw_filename).suffix.lower()
        allowed_extensions = {ext.lower() for ext in settings.ALLOWED_EXTENSIONS}
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types: {', '.join(sorted(allowed_extensions))}",
            )

        content_type = (file.content_type or "").lower().strip()
        allowed_mime_types = {mime.lower() for mime in settings.ALLOWED_UPLOAD_MIME_TYPES}
        if content_type and content_type not in allowed_mime_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid content type. Allowed types: {', '.join(sorted(allowed_mime_types))}",
            )

    @staticmethod
    def _validate_magic_bytes(file_ext: str, header: bytes) -> None:
        signatures = MAGIC_SIGNATURES.get(file_ext)
        if not signatures:
            return
        if not any(header.startswith(signature) for signature in signatures):
            raise HTTPException(status_code=400, detail="Uploaded file content does not match file type")

    @staticmethod
    async def _save_document(user_id: int, file: UploadFile) -> str:
        """
        Save uploaded document to filesystem.

        Args:
            user_id: ID of user uploading the document
            file: Uploaded file

        Returns:
            Relative path to saved document

        Raises:
            HTTPException: If file save fails
        """
        try:
            upload_root = LicenseService._upload_root()
            upload_dir = upload_root / "licenses" / str(user_id)
            upload_dir.mkdir(parents=True, exist_ok=True)

            # Keep sortable timestamps but add entropy to avoid same-second collisions.
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            original_filename = Path(file.filename).name
            file_ext = Path(file.filename).suffix.lower()
            max_upload_size_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
            for _ in range(UPLOAD_FILENAME_MAX_ATTEMPTS):
                unique_suffix = uuid4().hex[:UPLOAD_FILENAME_ENTROPY_LENGTH]
                safe_filename = f"{timestamp}_{unique_suffix}_{original_filename}"
                file_path = upload_dir / safe_filename
                size = 0

                try:
                    # Use "xb" to guarantee create-only writes (no silent overwrite).
                    async with aiofiles.open(file_path, "xb") as out_file:
                        while content := await file.read(CHUNK_SIZE):
                            if size == 0:
                                LicenseService._validate_magic_bytes(file_ext, content[:16])

                            size += len(content)
                            if size > max_upload_size_bytes:
                                # Clean up the partial file
                                await out_file.close()
                                if file_path.exists():
                                    os.remove(file_path)
                                raise HTTPException(
                                    status_code=400,
                                    detail=f"File too large. Limit: {settings.MAX_UPLOAD_SIZE_MB}MB"
                                )
                            await out_file.write(content)
                except FileExistsError:
                    continue
                except HTTPException:
                    if file_path.exists():
                        os.remove(file_path)
                    raise

                if size == 0:
                    if file_path.exists():
                        os.remove(file_path)
                    raise HTTPException(status_code=400, detail="Uploaded file is empty")

                return file_path.relative_to(upload_root).as_posix()

            raise HTTPException(status_code=500, detail="Failed to generate unique upload filename")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to save license document: {e}")
            if 'file_path' in locals() and file_path.exists():
                os.remove(file_path)
            raise HTTPException(status_code=500, detail="Failed to save document")
        finally:
            await file.seek(0)

    @staticmethod
    async def submit_license(
        db: Session,
        user_id: int,
        data: LicenseCreate,
        file: UploadFile,
    ) -> License:
        """
        Submit a new license for verification.

        Args:
            db: Database session
            user_id: ID of user submitting license
            data: License data
            file: Uploaded license document

        Returns:
            Created License object

        Raises:
            HTTPException: If validation fails or duplicate exists
        """
        LicenseService._validate_file(file)

        # Check for any existing license for same advisor + state.
        existing = (
            db.query(License)
            .filter(
                and_(
                    License.user_id == user_id,
                    License.state == data.state.upper(),
                )
            )
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"You already have a license for state {data.state.upper()}",
            )

        # Check for duplicate license_number + state (across all users)
        duplicate = (
            db.query(License)
            .filter(
                and_(
                    License.state == data.state.upper(),
                    License.license_number == data.license_number.strip(),
                )
            )
            .first()
        )

        if duplicate:
            raise HTTPException(
                status_code=400,
                detail=f"License {data.license_number} for state {data.state} already exists",
            )

        # 2. Heavy I/O (Async)
        document_path = await LicenseService._save_document(user_id, file)

        # 3. Create Record
        try:
            license = License(
                user_id=user_id,
                state=data.state.upper(),
                license_number=data.license_number.strip(),
                license_type=data.license_type,
                document_path=document_path,
                verification_status="pending",
            )
            db.add(license)
            db.commit()
            db.refresh(license)
            
            logger.info(f"License submitted: {license.id}")
            return license
        except IntegrityError as exc:
            db.rollback()
            try:
                if document_path:
                    LicenseService._delete_document_if_safe(document_path)
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup document after error: {cleanup_error}")

            if LicenseService._is_unique_constraint_error(
                exc,
                constraint_names=("uq_licenses_user_state",),
                required_terms=("licenses.user_id", "licenses.state"),
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"You already have a license for state {data.state.upper()}",
                ) from exc
            if LicenseService._is_unique_constraint_error(
                exc,
                constraint_names=("uq_licenses_state_number",),
                required_terms=("licenses.state", "licenses.license_number"),
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"License {data.license_number} for state {data.state.upper()} already exists",
                ) from exc

            logger.error(f"Failed to create license due to integrity error: {exc}")
            raise HTTPException(status_code=500, detail="Failed to create license") from exc
        except Exception as e:
            db.rollback()
            # Try to delete uploaded file if database operation failed
            try:
                if document_path:
                    LicenseService._delete_document_if_safe(document_path)
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup document after error: {cleanup_error}")
            
            logger.error(f"Failed to create license: {e}")
            raise HTTPException(status_code=500, detail="Failed to create license")

    @staticmethod
    async def resubmit_rejected_license(
        db: Session,
        user_id: int,
        license_id: int,
        file: UploadFile,
        license_type: Optional[str] = None,
    ) -> License:
        """
        Resubmit a rejected license by replacing its document and returning it to pending.
        """
        license = db.query(License).filter(License.id == license_id).first()

        if not license:
            raise HTTPException(status_code=404, detail="License not found")

        if license.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to resubmit this license")

        if license.verification_status != "rejected":
            raise HTTPException(status_code=400, detail="Only rejected licenses can be resubmitted")

        pending_for_state = (
            db.query(License)
            .filter(
                and_(
                    License.user_id == user_id,
                    License.state == license.state,
                    License.verification_status == "pending",
                    License.id != license.id,
                )
            )
            .first()
        )
        if pending_for_state:
            raise HTTPException(
                status_code=400,
                detail=f"You already have a pending license for state {license.state}",
            )

        window_start = datetime.now(timezone.utc) - timedelta(
            days=settings.LICENSE_RESUBMISSION_WINDOW_DAYS
        )
        resubmission_count = (
            db.query(LicenseResubmission)
            .filter(
                and_(
                    LicenseResubmission.license_id == license.id,
                    LicenseResubmission.attempted_at >= window_start,
                )
            )
            .count()
        )

        if resubmission_count >= settings.LICENSE_RESUBMISSION_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=429,
                detail=(
                    "Resubmission limit reached for this license. "
                    "Please contact support or wait for the retry window to reset."
                ),
            )

        LicenseService._validate_file(file)
        document_path = await LicenseService._save_document(user_id, file)
        previous_document_path = license.document_path

        try:
            license.document_path = document_path
            license.verification_status = "pending"
            license.rejection_reason = None
            license.verified_at = None
            license.verified_by = None
            license.reviewed_at = None
            license.reviewed_by = None

            if license_type is not None:
                normalized_type = license_type.strip()
                license.license_type = normalized_type or None

            db.add(
                LicenseResubmission(
                    license_id=license.id,
                    user_id=user_id,
                )
            )
            AuditService.log_event(
                db=db,
                actor_user_id=user_id,
                action="license_resubmitted",
                entity_type="License",
                entity_id=license.id,
                meta_data={"state": license.state},
            )
            db.commit()
            db.refresh(license)

            if previous_document_path and previous_document_path != document_path:
                LicenseService._delete_document_if_safe(previous_document_path)

            logger.info(f"License resubmitted: license_id={license_id}, user_id={user_id}")
            return license
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            try:
                if document_path:
                    LicenseService._delete_document_if_safe(document_path)
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup resubmitted document after error: {cleanup_error}")
            logger.error(f"Failed to resubmit license: {e}")
            raise HTTPException(status_code=500, detail="Failed to resubmit license")

    @staticmethod
    def approve_license(db: Session, license_id: int, admin_id: int) -> License:
        """
        Approve a pending license.

        Args:
            db: Database session
            license_id: ID of license to approve
            admin_id: ID of admin user approving

        Returns:
            Updated License object

        Raises:
            HTTPException: If license not found or not pending
        """
        license = db.query(License).filter(License.id == license_id).first()

        if not license:
            raise HTTPException(status_code=404, detail="License not found")

        if license.verification_status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot approve license with status '{license.verification_status}'",
            )

        try:
            license.verification_status = "verified"
            license.verified_at = datetime.now(timezone.utc)
            license.verified_by = admin_id
            license.rejection_reason = None  # Clear any previous rejection reason
            license.reviewed_at = license.verified_at
            license.reviewed_by = admin_id

            AuditService.log_event(
                db=db,
                actor_user_id=admin_id,
                action="license_approved",
                entity_type="License",
                entity_id=license.id,
                meta_data={"state": license.state, "status": license.verification_status},
            )
            db.commit()
            db.refresh(license)

            logger.info(f"License approved: license_id={license_id}, admin_id={admin_id}")
            return license

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to approve license: {e}")
            raise HTTPException(status_code=500, detail="Failed to approve license")

    @staticmethod
    def reject_license(
        db: Session,
        license_id: int,
        admin_id: int,
        reason: str,
    ) -> License:
        """
        Reject a pending license.

        Args:
            db: Database session
            license_id: ID of license to reject
            admin_id: ID of admin user rejecting
            reason: Reason for rejection

        Returns:
            Updated License object

        Raises:
            HTTPException: If license not found or not pending
        """
        license = db.query(License).filter(License.id == license_id).first()

        if not license:
            raise HTTPException(status_code=404, detail="License not found")

        if license.verification_status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reject license with status '{license.verification_status}'",
            )

        try:
            license.verification_status = "rejected"
            license.rejection_reason = reason
            license.verified_at = None
            license.verified_by = None
            license.reviewed_at = datetime.now(timezone.utc)
            license.reviewed_by = admin_id

            AuditService.log_event(
                db=db,
                actor_user_id=admin_id,
                action="license_rejected",
                entity_type="License",
                entity_id=license.id,
                meta_data={
                    "state": license.state,
                    "status": license.verification_status,
                    "reason": reason,
                },
            )
            db.commit()
            db.refresh(license)

            logger.info(f"License rejected: license_id={license_id}, admin_id={admin_id}, reason={reason}")
            return license

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to reject license: {e}")
            raise HTTPException(status_code=500, detail="Failed to reject license")

    @staticmethod
    def get_user_licenses(db: Session, user_id: int) -> List[License]:
        """
        Get all licenses for a user.

        Args:
            db: Database session
            user_id: ID of user

        Returns:
            List of License objects ordered by created_at desc
        """
        return (
            db.query(License)
            .filter(License.user_id == user_id)
            .order_by(License.created_at.desc())
            .all()
        )

    @staticmethod
    def get_pending_licenses(db: Session) -> List[License]:
        """
        Get all pending licenses (admin view).

        Args:
            db: Database session

        Returns:
            List of pending License objects with user details
        """
        return (
            db.query(License)
            .join(User, License.user_id == User.id)
            .filter(License.verification_status == "pending")
            .order_by(License.created_at.asc())
            .all()
        )

    @staticmethod
    def get_processed_licenses(
        db: Session,
        advisor_id: Optional[int] = None,
        advisor_query: Optional[str] = None,
    ) -> List[dict]:
        """
        Get all currently processed licenses (admin view).

        Processed means the latest status is approved or rejected.
        """
        resubmission_counts = (
            db.query(
                LicenseResubmission.license_id.label("license_id"),
                func.count(LicenseResubmission.id).label("resubmission_count"),
            )
            .group_by(LicenseResubmission.license_id)
            .subquery()
        )

        query = (
            db.query(
                License,
                User.name.label("user_name"),
                User.email.label("user_email"),
                func.coalesce(resubmission_counts.c.resubmission_count, 0).label(
                    "resubmission_count"
                ),
            )
            .join(User, License.user_id == User.id)
            .outerjoin(
                resubmission_counts,
                resubmission_counts.c.license_id == License.id,
            )
            .filter(License.verification_status.in_(["verified", "rejected"]))
        )

        if advisor_id is not None:
            query = query.filter(License.user_id == advisor_id)

        normalized_query = advisor_query.strip() if advisor_query else ""
        if normalized_query:
            term = f"%{normalized_query}%"
            query = query.filter((User.name.ilike(term)) | (User.email.ilike(term)))

        rows = (
            query.order_by(License.reviewed_at.desc(), License.created_at.desc())
            .all()
        )

        processed_rows: List[dict] = []
        for license, user_name, user_email, resubmission_count in rows:
            count = int(resubmission_count or 0)
            processed_rows.append(
                {
                    "license": license,
                    "user_name": user_name,
                    "user_email": user_email,
                    "submission_type": "resubmission" if count > 0 else "first_time",
                    "review_cycle": count + 1,
                }
            )

        return processed_rows

    @staticmethod
    def get_license_by_id(db: Session, license_id: int) -> Optional[License]:
        """
        Get license by ID.

        Args:
            db: Database session
            license_id: ID of license

        Returns:
            License object or None if not found
        """
        return db.query(License).filter(License.id == license_id).first()

    @staticmethod
    def resolve_document_for_download(document_path: Optional[str]) -> tuple[Path, str]:
        """
        Resolve and validate a stored license document path for secure downloads.

        Args:
            document_path: Stored file path from license record

        Returns:
            Tuple of resolved file path and media type

        Raises:
            HTTPException: If the path is invalid, outside upload dir, missing, or unsupported
        """
        if not document_path:
            raise HTTPException(status_code=404, detail="Document not available")

        candidate = LicenseService._resolve_stored_document_path(document_path)

        if not candidate.exists() or not candidate.is_file():
            raise HTTPException(status_code=404, detail="Document file not found")

        file_ext = candidate.suffix.lower()
        allowed_extensions = {ext.lower() for ext in settings.ALLOWED_EXTENSIONS}
        if file_ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail="Document type is not allowed")

        media_type = EXTENSION_TO_MIME.get(file_ext)
        if not media_type:
            raise HTTPException(status_code=400, detail="Unsupported document type")

        return candidate, media_type

    @staticmethod
    def _delete_document_if_safe(document_path: Optional[str]) -> None:
        if not document_path:
            return

        try:
            resolved_path, _ = LicenseService.resolve_document_for_download(document_path)
        except HTTPException as exc:
            # Missing files are already effectively deleted.
            if exc.status_code != 404:
                logger.error(f"Skipped unsafe document cleanup for path: {document_path}")
            return

        try:
            os.remove(resolved_path)
        except Exception as cleanup_error:
            logger.error(f"Failed to cleanup document: {cleanup_error}")
