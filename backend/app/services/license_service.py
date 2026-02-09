import os
import logging
import aiofiles
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.license import License
from app.models.user import User
from app.core.config import settings
from app.schemas.license import LicenseCreate

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024  # 1 MB chunks
MAGIC_SIGNATURES = {
    ".pdf": (b"%PDF-",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
}

class LicenseService:
    """Service for managing license verification workflow."""

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
            upload_dir = Path(settings.UPLOAD_DIR) / "licenses" / str(user_id)
            upload_dir.mkdir(parents=True, exist_ok=True)

            # Generate unique filename with timestamp
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            
            safe_filename = f"{timestamp}_{Path(file.filename).name}"
            file_path = upload_dir / safe_filename

            size = 0
            file_ext = Path(file.filename).suffix.lower()
            # Use aiofiles for non-blocking disk I/O
            async with aiofiles.open(file_path, "wb") as out_file:
                while content := await file.read(CHUNK_SIZE):
                    if size == 0:
                        LicenseService._validate_magic_bytes(file_ext, content[:16])

                    size += len(content)
                    if size > settings.MAX_UPLOAD_SIZE_MB:
                        # Clean up the partial file
                        await out_file.close()
                        if file_path.exists():
                            os.remove(file_path)
                        raise HTTPException(
                            status_code=400, 
                            detail=f"File too large. Limit: {settings.MAX_UPLOAD_SIZE_MB/1024/1024}MB"
                        )
                    await out_file.write(content)

            if size == 0:
                if file_path.exists():
                    os.remove(file_path)
                raise HTTPException(status_code=400, detail="Uploaded file is empty")

            return str(file_path)

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

        # Check for duplicate pending license for same user + state
        existing = (
            db.query(License)
            .filter(
                and_(
                    License.user_id == user_id,
                    License.state == data.state.upper(),
                    License.verification_status == "pending",
                )
            )
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"You already have a pending license for state {data.state}",
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
        
        except Exception as e:
            db.rollback()
            # Try to delete uploaded file if database operation failed
            try:
                if document_path and os.path.exists(document_path):
                    os.remove(document_path)
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup document after error: {cleanup_error}")
            
            logger.error(f"Failed to create license: {e}")
            raise HTTPException(status_code=500, detail="Failed to create license")

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
