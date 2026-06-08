"""Integration execution endpoints: execute confirmed actions from Command Center."""

import io
import uuid
from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.config import settings
from docere.dependencies import get_db, require_instructor
from docere.models.calendar import InstructorCalendarToken

logger = structlog.get_logger()

router = APIRouter()


# ── Status ──


class IntegrationStatus(BaseModel):
    google_connected: bool
    google_scopes: list[str]
    lms_type: str | None  # "moodle" | "canvas" | None
    lms_connected: bool


@router.get("/status", response_model=IntegrationStatus)
async def get_integration_status(
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> IntegrationStatus:
    """Return which integrations the instructor has connected."""
    result = await db.execute(
        select(InstructorCalendarToken).where(
            InstructorCalendarToken.instructor_id == user_id,
            InstructorCalendarToken.is_active == True,  # noqa: E712
        )
    )
    google_token = result.scalar_one_or_none()
    google_connected = google_token is not None
    google_scopes = google_token.scopes.split(",") if google_token and google_token.scopes else []

    lms_type: str | None = None
    lms_connected = False
    if settings.moodle_base_url and settings.moodle_api_token:
        lms_type = "moodle"
        lms_connected = True
    elif settings.canvas_base_url and settings.canvas_api_token:
        lms_type = "canvas"
        lms_connected = True

    return IntegrationStatus(
        google_connected=google_connected,
        google_scopes=google_scopes,
        lms_type=lms_type,
        lms_connected=lms_connected,
    )


# ── Execute ──


class ExecuteActionRequest(BaseModel):
    action_type: str
    payload: dict[str, Any]


class ExecuteActionResponse(BaseModel):
    success: bool
    result: dict[str, Any] = {}
    error: str | None = None


@router.post("/execute", response_model=ExecuteActionResponse)
async def execute_action(
    request: ExecuteActionRequest,
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> ExecuteActionResponse:
    """Execute a confirmed action from the Command Center.

    The frontend shows a preview; user clicks Execute; this runs.
    """
    try:
        if request.action_type == "draft_email":
            return await _execute_email(str(user_id), request.payload, db)
        elif request.action_type == "create_doc":
            return await _execute_doc(str(user_id), request.payload, db)
        elif request.action_type == "create_sheet":
            return await _execute_sheet(str(user_id), request.payload, db)
        elif request.action_type == "lms_announcement":
            return await _execute_lms_announcement(request.payload)
        elif request.action_type == "calendar_event":
            return await _execute_calendar_event(str(user_id), request.payload, db)
        elif request.action_type == "create_excel":
            return await _execute_excel(request.payload)
        else:
            raise HTTPException(
                status_code=400, detail=f"Unknown action type: {request.action_type}"
            )
    except ValueError as e:
        return ExecuteActionResponse(success=False, error=str(e))
    except Exception as e:
        error_msg = str(e).lower()
        if "invalid_grant" in error_msg or "revoked" in error_msg:
            return ExecuteActionResponse(
                success=False,
                error=(
                    "Google connection expired. Please reconnect your Google account in Settings."
                ),
            )
        logger.error(
            "Action execution failed",
            action_type=request.action_type,
            error=str(e),
        )
        return ExecuteActionResponse(success=False, error=f"Failed to execute: {e}")


async def _resolve_email_recipients(
    to_field: str | list[str], course_id: str | None, db: AsyncSession
) -> list[str]:
    """Resolve group targets like 'all_students' or 'struggling_students' to actual emails.

    Supports:
    - "all_students" — every enrolled student with an email
    - "struggling_students" — high confusion (>0.5) or low/inactive engagement
    - "low_engagement" — low or inactive engagement
    - "at_risk" — grade below 70
    - Comma-separated student names — fuzzy matched against roster
    - A list of actual email addresses — passed through as-is
    """
    from docere.models.course import Enrollment
    from docere.models.memory import StudentProfile
    from docere.models.user import User

    # Already a list of emails
    if isinstance(to_field, list):
        return to_field

    target = to_field.strip().lower()

    if not course_id:
        raise ValueError("course_id is required to resolve student recipients")

    # Base query: enrolled students with emails
    base_query = (
        select(User.email, User.name, StudentProfile)
        .join(Enrollment, Enrollment.user_id == User.id)
        .outerjoin(
            StudentProfile,
            (StudentProfile.student_id == User.id) & (StudentProfile.course_id == course_id),
        )
        .where(
            Enrollment.course_id == course_id,
            Enrollment.lms_role == "student",
            User.email.isnot(None),
            User.email != "",
        )
    )

    result = await db.execute(base_query)
    rows = result.all()

    if target == "all_students":
        emails = [r.email for r in rows]
    elif target == "struggling_students":
        emails = [
            r.email
            for r in rows
            if r[2]
            and (r[2].avg_confusion_score > 0.5 or r[2].engagement_level in ("low", "inactive"))
        ]
    elif target == "low_engagement":
        emails = [r.email for r in rows if r[2] and r[2].engagement_level in ("low", "inactive")]
    elif target == "at_risk":
        emails = [
            r.email
            for r in rows
            if r[2] and r[2].current_grade is not None and r[2].current_grade < 70
        ]
    else:
        # Try to match comma-separated student names
        target_names = [n.strip().lower() for n in to_field.split(",")]
        emails = [r.email for r in rows if any(tn in r.name.lower() for tn in target_names)]

    if not emails:
        raise ValueError(f"No students matched target '{to_field}' (or none have email addresses)")

    return emails


async def _execute_email(
    instructor_id: str, payload: dict[str, Any], db: AsyncSession
) -> ExecuteActionResponse:
    from docere.services.google_gmail import GmailService

    # Resolve group targets to actual email addresses
    to_field = payload.get("to", [])
    course_id = payload.get("course_id")
    resolved_emails = await _resolve_email_recipients(to_field, course_id, db)

    svc = GmailService(db)
    result = await svc.send_email(
        instructor_id=instructor_id,
        to=resolved_emails,
        subject=payload.get("subject", ""),
        body=payload.get("body", ""),
        cc=payload.get("cc"),
        bcc=payload.get("bcc"),
    )
    result["recipients_count"] = len(resolved_emails)
    return ExecuteActionResponse(success=True, result=result)


async def _execute_doc(
    instructor_id: str, payload: dict[str, Any], db: AsyncSession
) -> ExecuteActionResponse:
    from docere.services.google_docs import GoogleDocsService

    svc = GoogleDocsService(db)
    result = await svc.create_document(
        instructor_id=instructor_id,
        title=payload.get("title", "Untitled"),
        content=payload.get("content", ""),
    )
    return ExecuteActionResponse(success=True, result=result)


async def _execute_sheet(
    instructor_id: str, payload: dict[str, Any], db: AsyncSession
) -> ExecuteActionResponse:
    from docere.services.google_sheets import GoogleSheetsService

    svc = GoogleSheetsService(db)
    result = await svc.create_spreadsheet(
        instructor_id=instructor_id,
        title=payload.get("title", "Untitled"),
        headers=payload.get("headers", []),
        rows=payload.get("rows", []),
        sheet_name=payload.get("sheet_name", "Sheet1"),
    )
    return ExecuteActionResponse(success=True, result=result)


async def _execute_lms_announcement(payload: dict[str, Any]) -> ExecuteActionResponse:
    course_external_id = payload.get("course_id", "")
    title = payload.get("title", "")
    message = payload.get("message", "")

    if settings.moodle_base_url and settings.moodle_api_token:
        from docere.integrations.lms.moodle import MoodleAdapter

        adapter = MoodleAdapter()
    elif settings.canvas_base_url and settings.canvas_api_token:
        from docere.integrations.lms.canvas import CanvasAdapter

        adapter = CanvasAdapter()
    else:
        raise ValueError("No LMS configured")

    result = await adapter.post_announcement(
        course_id=course_external_id,
        title=title,
        message=message,
    )
    return ExecuteActionResponse(success=True, result=result)


async def _execute_calendar_event(
    instructor_id: str, payload: dict[str, Any], db: AsyncSession
) -> ExecuteActionResponse:
    from docere.services.google_calendar import GoogleCalendarService

    svc = GoogleCalendarService(db)
    event_id = await svc.create_event(
        instructor_id=instructor_id,
        summary=payload.get("summary", ""),
        description=payload.get("description", ""),
        start=datetime.fromisoformat(payload["start"]),
        end=datetime.fromisoformat(payload["end"]),
        attendee_email=payload.get("attendee_email"),
    )
    return ExecuteActionResponse(
        success=event_id is not None,
        result={"event_id": event_id or ""},
    )


async def _execute_excel(payload: dict[str, Any]) -> ExecuteActionResponse:
    """Generate an Excel file and return a download token.

    The file is served via /download-excel/<filename> endpoint.
    """
    import openpyxl

    title = payload.get("title", "Export")
    headers = payload.get("headers", [])
    rows = payload.get("rows", [])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = title[:31]  # Excel sheet name limit

    if headers:
        ws.append(headers)
    for row in rows:
        ws.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    # Store in memory for download (simple approach)
    filename = f"{title.replace(' ', '_')}.xlsx"
    _excel_cache[filename] = buf.getvalue()

    return ExecuteActionResponse(
        success=True,
        result={
            "filename": filename,
            "download_url": f"/api/v1/integrations/download-excel/{filename}",
        },
    )


# Simple in-memory cache for generated Excel files
_excel_cache: dict[str, bytes] = {}


# ── Resolve Email Recipients ──


class ResolveRecipientsRequest(BaseModel):
    to: str
    course_id: str


class ResolveRecipientsResponse(BaseModel):
    count: int
    emails: list[str]
    target_label: str


_TARGET_LABELS = {
    "all_students": "All students",
    "struggling_students": "Struggling students",
    "low_engagement": "Low engagement students",
    "at_risk": "At-risk students (grade < 70)",
}


@router.post("/resolve-recipients", response_model=ResolveRecipientsResponse)
async def resolve_recipients(
    request: ResolveRecipientsRequest,
    _user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> ResolveRecipientsResponse:
    """Preview how many students match an email target before sending."""
    emails = await _resolve_email_recipients(request.to, request.course_id, db)
    label = _TARGET_LABELS.get(request.to.strip().lower(), request.to)
    return ResolveRecipientsResponse(
        count=len(emails),
        emails=emails,
        target_label=f"{label} ({len(emails)})",
    )


# ── Excel Upload ──

_upload_cache: dict[str, dict[str, Any]] = {}


@router.post("/upload-excel")
async def upload_excel(
    file: UploadFile = File(...),
    _user_id: uuid.UUID = Depends(require_instructor),
) -> dict[str, Any]:
    """Upload and parse an Excel file for gradebook sync.

    Returns a dict with keys: upload_id, filename, headers, rows, sheet_names.
    """
    import openpyxl

    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    wb = openpyxl.load_workbook(io.BytesIO(contents), read_only=True, data_only=True)
    sheet_names = wb.sheetnames

    # Read first sheet by default
    ws = wb.active
    rows_data: list[list[str]] = []
    for row in ws.iter_rows(values_only=True):
        rows_data.append([str(cell) if cell is not None else "" for cell in row])

    wb.close()

    # Auto-detect header row: skip title/merged rows and empty rows.
    # The header row is the first row with 2+ non-empty cells.
    header_idx = 0
    for idx, row in enumerate(rows_data):
        non_empty = sum(1 for c in row if c.strip())
        if non_empty >= 2:
            header_idx = idx
            break

    headers = rows_data[header_idx] if rows_data else []
    data_rows = rows_data[header_idx + 1 :] if len(rows_data) > header_idx + 1 else []

    # Strip trailing empty rows
    while data_rows and all(c.strip() == "" for c in data_rows[-1]):
        data_rows.pop()

    upload_id = str(uuid.uuid4())
    _upload_cache[upload_id] = {
        "filename": file.filename,
        "headers": headers,
        "rows": data_rows,
        "sheet_names": sheet_names,
    }

    return {
        "upload_id": upload_id,
        "filename": file.filename,
        "headers": headers,
        "rows": data_rows,
        "sheet_names": sheet_names,
    }


@router.get("/upload-excel/{upload_id}")
async def get_uploaded_excel(
    upload_id: str,
    _user_id: uuid.UUID = Depends(require_instructor),
) -> dict[str, Any]:
    """Retrieve previously uploaded Excel data by upload_id."""
    data = _upload_cache.get(upload_id)
    if not data:
        raise HTTPException(status_code=404, detail="Upload not found or expired")
    return data


@router.get("/download-excel/{filename}")
async def download_excel(
    filename: str,
    _user_id: uuid.UUID = Depends(require_instructor),
) -> StreamingResponse:
    """Download a generated Excel file."""
    data = _excel_cache.pop(filename, None)
    if not data:
        raise HTTPException(status_code=404, detail="File not found or already downloaded")

    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
