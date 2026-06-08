"""Gradebook Sync: validate, sync, and fix grades between spreadsheets and LMS."""

# E501 intentional here: file holds long prompt/instruction string constants.
# ruff: noqa: E501
import io
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from docere.config import settings
from docere.dependencies import get_claude, get_db, require_instructor
from docere.integrations.llm.client import ClaudeClient
from docere.models.course import Course

logger = structlog.get_logger()

router = APIRouter()


# ── Request / Response Models ──


class SpreadsheetData(BaseModel):
    title: str = ""
    headers: list[str] = []
    rows: list[list[str]] = []


class ReadSheetRequest(BaseModel):
    spreadsheet_id: str


class ReadSheetUrlRequest(BaseModel):
    url: str


class ValidateRequest(BaseModel):
    source_data: SpreadsheetData
    course_id: str
    grade_item_ids: list[str] = []


class ValidationIssue(BaseModel):
    row: int
    col: int
    type: str  # "missing_student", "invalid_grade", "format_error", "mismatch"
    current: str
    expected: str
    suggestion: str


class ColumnMapping(BaseModel):
    student_name_col: int
    grade_columns: dict[str, int]  # grade_item_id -> col index


class ValidationResult(BaseModel):
    valid: bool
    mappings: ColumnMapping | None = None
    issues: list[ValidationIssue] = []
    preview: list[dict[str, Any]] = []
    student_count: int = 0


class SyncRequest(BaseModel):
    course_id: str
    mappings: ColumnMapping
    source_data: SpreadsheetData
    skip_rows: list[int] = []


class SyncResult(BaseModel):
    synced: int
    failed: int
    errors: list[dict[str, Any]] = []


class FixRequest(BaseModel):
    source_data: SpreadsheetData
    issues: list[ValidationIssue]


class FixResult(BaseModel):
    fixed_data: SpreadsheetData
    changes: list[dict[str, Any]] = []


# ── Google Sheets Sources ──


@router.get("/sources/google")
async def list_google_spreadsheets(
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List Docere-created Google Sheets for this instructor."""
    from docere.services.google_sheets import GoogleSheetsService

    svc = GoogleSheetsService(db)
    try:
        return await svc.list_spreadsheets(str(user_id))
    except ValueError:
        # Google not connected — return empty list instead of error
        return []
    except Exception as e:
        logger.warning("Failed to list Google spreadsheets", error=str(e))
        return []


@router.post("/sources/google/read")
async def read_google_spreadsheet(
    request: ReadSheetRequest,
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Read data from a Google Sheet by spreadsheet ID."""
    from docere.services.google_sheets import GoogleSheetsService

    svc = GoogleSheetsService(db)
    try:
        return await svc.read_spreadsheet(str(user_id), request.spreadsheet_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to read Google spreadsheet", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to read spreadsheet: {e}")


@router.post("/sources/google/read-url")
async def read_google_spreadsheet_url(
    request: ReadSheetUrlRequest,
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Read data from a Google Sheet by URL."""
    from docere.services.google_sheets import GoogleSheetsService

    svc = GoogleSheetsService(db)
    try:
        return await svc.read_from_url(str(user_id), request.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to read Google spreadsheet from URL", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to read spreadsheet: {e}")


# ── LMS Destinations ──


def _get_lms_adapter():
    """Get the configured LMS adapter."""
    if settings.moodle_base_url and settings.moodle_api_token:
        from docere.integrations.lms.moodle import MoodleAdapter

        return MoodleAdapter()
    elif settings.canvas_base_url and settings.canvas_api_token:
        from docere.integrations.lms.canvas import CanvasAdapter

        return CanvasAdapter()
    return None


@router.get("/destinations/{course_id}/grade-items")
async def get_grade_items(
    course_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get assignment/grade items from the LMS for a course."""
    course = await db.get(Course, course_id)
    if not course or not course.external_lms_id:
        raise HTTPException(status_code=404, detail="Course not found or not linked to LMS")

    adapter = _get_lms_adapter()
    if not adapter:
        raise HTTPException(status_code=400, detail="No LMS configured")

    return await adapter.get_grade_items(course.external_lms_id)


# ── Validate ──


def _normalize(s: str) -> str:
    """Lowercase, strip, remove common prefixes like 'Assignment:' for comparison."""
    s = s.lower().strip()
    # Remove numbering prefixes like "1. ", "1) "
    import re as _re

    s = _re.sub(r"^\d+[\.\)]\s*", "", s)
    return s


def _find_student_column(headers: list[str], sample_rows: list[list[str]]) -> int | None:
    """Heuristically find the student name column."""
    name_keywords = {"student", "name", "student name", "full name", "learner"}
    for i, h in enumerate(headers):
        if _normalize(h) in name_keywords or any(k in _normalize(h) for k in name_keywords):
            return i

    # Fallback: find the column where most values look like names (contain a space, mostly alpha)
    for i, h in enumerate(headers):
        if not sample_rows:
            break
        values = [row[i] for row in sample_rows if i < len(row)]
        if values and all(
            " " in v and not v.replace(" ", "").replace(".", "").replace("-", "").isdigit()
            for v in values
            if v.strip()
        ):
            return i
    return None


def _match_headers_to_items(
    headers: list[str], grade_items: list[dict[str, Any]]
) -> dict[str, int]:
    """Deterministically match spreadsheet headers to grade items by name similarity.

    Returns {grade_item_id: column_index}.
    """
    matched: dict[str, int] = {}
    used_cols: set[int] = set()

    for item in grade_items:
        item_name = _normalize(item["name"])
        best_col = None
        best_score = 0

        for col_idx, header in enumerate(headers):
            if col_idx in used_cols:
                continue
            header_norm = _normalize(header)
            if not header_norm:
                continue

            # Exact match
            if header_norm == item_name:
                best_col = col_idx
                best_score = 100
                break

            # One contains the other
            if header_norm in item_name or item_name in header_norm:
                score = 80
                if score > best_score:
                    best_col = col_idx
                    best_score = score

            # Significant word overlap
            header_words = set(header_norm.split())
            item_words = set(item_name.split())
            if header_words and item_words:
                overlap = header_words & item_words
                overlap_ratio = len(overlap) / max(len(header_words), len(item_words))
                if overlap_ratio >= 0.5:
                    score = int(60 * overlap_ratio)
                    if score > best_score:
                        best_col = col_idx
                        best_score = score

        if best_col is not None and best_score >= 30:
            matched[item["id"]] = best_col
            used_cols.add(best_col)

    return matched


VALIDATE_SYSTEM_PROMPT = """You are a data validation assistant. You analyze spreadsheet data and identify how columns map to gradebook items.

Given:
1. Spreadsheet headers and sample rows
2. List of LMS grade items (assignments) with their IDs and names

Your job: Identify which spreadsheet column contains student names/IDs, and which columns map to which grade items.

Rules:
- Match columns by name similarity (e.g. "Assignment 1" matches "Assignment 1", "HW 1" might match "Homework 1")
- The student column usually contains names or student IDs
- Grade columns contain numeric values (scores/percentages)
- If a column clearly doesn't match any grade item, skip it
- IMPORTANT: Use the grade item's ID (the numeric ID), NOT the name, as the key in grade_columns

Respond in this exact JSON format:
{"student_name_col": <column_index>, "grade_columns": {"<grade_item_id>": <column_index>, ...}}

Column indices are 0-based. Only include confident matches. The grade_item_id MUST be the numeric ID provided in the grade items list, not the assignment name."""


@router.post("/validate", response_model=ValidationResult)
async def validate_gradebook(
    request: ValidateRequest,
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
    claude: ClaudeClient = Depends(get_claude),
) -> ValidationResult:
    """Validate spreadsheet data against LMS gradebook."""
    import json

    course = await db.get(Course, uuid.UUID(request.course_id))
    if not course or not course.external_lms_id:
        raise HTTPException(status_code=404, detail="Course not found or not linked to LMS")

    adapter = _get_lms_adapter()
    if not adapter:
        raise HTTPException(status_code=400, detail="No LMS configured")

    # Fetch grade items and enrollments from LMS
    grade_items = await adapter.get_grade_items(course.external_lms_id)
    enrollments = await adapter.get_enrollments(course.external_lms_id)

    # Filter to selected grade items if specified
    if request.grade_item_ids:
        grade_items = [g for g in grade_items if g["id"] in request.grade_item_ids]

    if not grade_items:
        raise HTTPException(status_code=400, detail="No grade items selected")

    # Build enrollment lookup (name -> LMS user ID)
    enrollment_map: dict[str, str] = {}
    for e in enrollments:
        enrollment_map[e.name.lower().strip()] = e.user_id

    # ── Column mapping: deterministic match first, Claude fallback ──
    headers = request.source_data.headers
    grade_item_map = {g["id"]: g for g in grade_items}

    # Step 1: Find student name column (heuristic)
    student_col = _find_student_column(headers, request.source_data.rows[:5])

    # Step 2: Match spreadsheet headers to grade items by name similarity
    fixed_grade_columns = _match_headers_to_items(headers, grade_items)

    logger.info(
        "Deterministic mapping result",
        student_col=student_col,
        matched=fixed_grade_columns,
        headers=headers,
        grade_items=[{"id": g["id"], "name": g["name"]} for g in grade_items],
    )

    # Step 3: If deterministic matching found nothing, try Claude as fallback
    if not fixed_grade_columns:
        logger.info("Deterministic matching failed, trying Claude fallback")
        sample_rows = request.source_data.rows[:5]
        mapping_prompt = f"Spreadsheet headers: {headers}\nSample rows (first 5):\n"
        for row in sample_rows:
            mapping_prompt += f"  {row}\n"
        mapping_prompt += "\nGrade items in LMS:\n"
        for item in grade_items:
            mapping_prompt += (
                f"  - ID: {item['id']}, Name: {item['name']}, Max: {item.get('grade_max', 100)}\n"
            )
        mapping_prompt += "\nIdentify the column mappings."

        mapping_text = await claude.chat(
            system_prompt=VALIDATE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": mapping_prompt}],
            max_tokens=500,
            temperature=0.1,
        )
        logger.info("Claude mapping response", response=mapping_text)

        try:
            json_start = mapping_text.find("{")
            json_end = mapping_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                mapping_json = json.loads(mapping_text[json_start:json_end])
                if student_col is None and "student_name_col" in mapping_json:
                    student_col = int(mapping_json["student_name_col"])

                # Try to resolve Claude's grade_columns keys
                grade_item_by_name = {g["name"].lower().strip(): g for g in grade_items}
                for key, col_idx in mapping_json.get("grade_columns", {}).items():
                    key_str = str(key)
                    col = int(col_idx)
                    if key_str in grade_item_map:
                        fixed_grade_columns[key_str] = col
                    elif key_str.lower().strip() in grade_item_by_name:
                        fixed_grade_columns[grade_item_by_name[key_str.lower().strip()]["id"]] = col
                    else:
                        # Partial match
                        for item_name, item in grade_item_by_name.items():
                            if key_str.lower() in item_name or item_name in key_str.lower():
                                fixed_grade_columns[item["id"]] = col
                                break
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Claude fallback parsing failed", error=str(e))

    if student_col is None:
        student_col = 0  # Default to first column

    # Step 4: If still no matches, try auto-assigning numeric columns to unmatched items
    if not fixed_grade_columns:
        matched_cols = {student_col}
        # Find columns that look numeric (check sample rows)
        numeric_cols: list[int] = []
        for col_idx in range(len(headers)):
            if col_idx in matched_cols:
                continue
            # Check if most values in this column are numeric
            numeric_count = 0
            total = 0
            for row in request.source_data.rows[:10]:
                if col_idx < len(row) and row[col_idx].strip():
                    total += 1
                    val = row[col_idx].strip().rstrip("%")
                    if "/" in val:
                        val = val.split("/")[0].strip()
                    try:
                        float(val)
                        numeric_count += 1
                    except ValueError:
                        pass
            if total > 0 and numeric_count / total >= 0.5:
                numeric_cols.append(col_idx)

        unmatched_items = [g for g in grade_items if g["id"] not in fixed_grade_columns]

        if len(unmatched_items) == 1 and len(numeric_cols) == 1:
            # Only one grade item and one numeric column — obvious match
            fixed_grade_columns[unmatched_items[0]["id"]] = numeric_cols[0]
            logger.info(
                "Auto-assigned single grade column",
                item=unmatched_items[0]["name"],
                col=numeric_cols[0],
            )
        elif len(unmatched_items) == len(numeric_cols) and len(numeric_cols) > 0:
            # Same number of items and numeric columns — assign in order
            for item, col in zip(unmatched_items, numeric_cols):
                fixed_grade_columns[item["id"]] = col
            logger.info("Auto-assigned grade columns by position", count=len(numeric_cols))

    if not fixed_grade_columns:
        raise HTTPException(
            status_code=422,
            detail="Could not match any spreadsheet columns to gradebook items. "
            "Make sure your spreadsheet column headers include the assignment names "
            f"(e.g. {', '.join(g['name'] for g in grade_items[:3])}).",
        )

    mappings = ColumnMapping(
        student_name_col=student_col,
        grade_columns=fixed_grade_columns,
    )

    # Validate row by row
    issues: list[ValidationIssue] = []
    preview: list[dict[str, Any]] = []

    for row_idx, row in enumerate(request.source_data.rows):
        # Get student name
        if mappings.student_name_col >= len(row):
            issues.append(
                ValidationIssue(
                    row=row_idx,
                    col=mappings.student_name_col,
                    type="format_error",
                    current="",
                    expected="Student name",
                    suggestion="Row is missing student name column",
                )
            )
            continue

        student_name = row[mappings.student_name_col].strip()
        if not student_name:
            continue  # Skip empty rows

        # Match student to enrollment
        student_lms_id = enrollment_map.get(student_name.lower())
        if not student_lms_id:
            # Try partial match
            for enrolled_name, lms_id in enrollment_map.items():
                if student_name.lower() in enrolled_name or enrolled_name in student_name.lower():
                    student_lms_id = lms_id
                    break

        if not student_lms_id:
            issues.append(
                ValidationIssue(
                    row=row_idx,
                    col=mappings.student_name_col,
                    type="missing_student",
                    current=student_name,
                    expected="Enrolled student name",
                    suggestion=f"'{student_name}' not found in course roster",
                )
            )
            continue

        # Validate each grade column
        student_preview: dict[str, Any] = {
            "student": student_name,
            "student_lms_id": student_lms_id,
            "grades": [],
        }
        for item_id, col_idx in mappings.grade_columns.items():
            item = grade_item_map.get(item_id)
            if not item:
                logger.warning("Mapped grade item not found", item_id=item_id)
                continue

            if col_idx >= len(row):
                issues.append(
                    ValidationIssue(
                        row=row_idx,
                        col=col_idx,
                        type="format_error",
                        current="",
                        expected=f"Grade for {item['name']}",
                        suggestion="Missing grade column value",
                    )
                )
                continue

            cell_value = row[col_idx].strip()
            if not cell_value:
                continue  # Empty grade = skip

            # Try to parse as number
            cleaned = cell_value.rstrip("%").strip()
            # Handle fractions like "85/100"
            if "/" in cleaned:
                parts = cleaned.split("/")
                try:
                    cleaned = str(float(parts[0].strip()))
                except ValueError:
                    pass

            try:
                grade_val = float(cleaned)
                grade_max = item.get("grade_max", 100)
                if grade_val < 0:
                    issues.append(
                        ValidationIssue(
                            row=row_idx,
                            col=col_idx,
                            type="invalid_grade",
                            current=cell_value,
                            expected=f"0-{grade_max}",
                            suggestion="Grade cannot be negative",
                        )
                    )
                elif grade_val > grade_max:
                    issues.append(
                        ValidationIssue(
                            row=row_idx,
                            col=col_idx,
                            type="invalid_grade",
                            current=cell_value,
                            expected=f"0-{grade_max}",
                            suggestion=f"Grade exceeds maximum ({grade_max})",
                        )
                    )
                else:
                    student_preview["grades"].append(
                        {
                            "item": item["name"],
                            "item_id": item_id,
                            "new": grade_val,
                        }
                    )
            except ValueError:
                issues.append(
                    ValidationIssue(
                        row=row_idx,
                        col=col_idx,
                        type="format_error",
                        current=cell_value,
                        expected="Numeric grade",
                        suggestion=f"'{cell_value}' is not a valid number — use a numeric value (e.g. 85, 92.5)",
                    )
                )

        if student_preview["grades"]:
            preview.append(student_preview)

    return ValidationResult(
        valid=len(issues) == 0,
        mappings=mappings,
        issues=issues,
        preview=preview,
        student_count=len(preview),
    )


# ── Sync ──


@router.post("/sync", response_model=SyncResult)
async def sync_gradebook(
    request: SyncRequest,
    user_id: uuid.UUID = Depends(require_instructor),
    db: AsyncSession = Depends(get_db),
) -> SyncResult:
    """Push validated grades to the LMS gradebook."""
    course = await db.get(Course, uuid.UUID(request.course_id))
    if not course or not course.external_lms_id:
        raise HTTPException(status_code=404, detail="Course not found or not linked to LMS")

    adapter = _get_lms_adapter()
    if not adapter:
        raise HTTPException(status_code=400, detail="No LMS configured")

    # Build enrollment lookup
    enrollments = await adapter.get_enrollments(course.external_lms_id)
    enrollment_map: dict[str, str] = {}
    for e in enrollments:
        enrollment_map[e.name.lower().strip()] = e.user_id

    synced = 0
    failed = 0
    errors: list[dict[str, Any]] = []

    for row_idx, row in enumerate(request.source_data.rows):
        if row_idx in request.skip_rows:
            continue

        if request.mappings.student_name_col >= len(row):
            continue

        student_name = row[request.mappings.student_name_col].strip()
        if not student_name:
            continue

        # Match student
        student_lms_id = enrollment_map.get(student_name.lower())
        if not student_lms_id:
            for enrolled_name, lms_id in enrollment_map.items():
                if student_name.lower() in enrolled_name or enrolled_name in student_name.lower():
                    student_lms_id = lms_id
                    break
        if not student_lms_id:
            continue

        # Save each grade
        for item_id, col_idx in request.mappings.grade_columns.items():
            if col_idx >= len(row):
                continue

            cell_value = row[col_idx].strip()
            if not cell_value:
                continue

            # Parse grade value — match validation logic
            cleaned = cell_value.rstrip("%").strip()
            if "/" in cleaned:
                parts = cleaned.split("/")
                try:
                    cleaned = str(float(parts[0].strip()))
                except ValueError:
                    pass

            try:
                grade_val = float(cleaned)
            except ValueError:
                failed += 1
                errors.append(
                    {
                        "student": student_name,
                        "item_id": item_id,
                        "error": f"'{cell_value}' is not a valid number",
                    }
                )
                continue

            try:
                await adapter.save_grade(
                    course_id=course.external_lms_id,
                    assignment_id=item_id,
                    student_id=student_lms_id,
                    grade=grade_val,
                )
                synced += 1
            except Exception as e:
                failed += 1
                errors.append(
                    {
                        "student": student_name,
                        "item_id": item_id,
                        "error": str(e),
                    }
                )
                logger.warning(
                    "Grade sync failed",
                    student=student_name,
                    item_id=item_id,
                    error=str(e),
                )

    return SyncResult(synced=synced, failed=failed, errors=errors)


# ── Fix ──


FIX_SYSTEM_PROMPT = """You are a data correction assistant. Given a spreadsheet with validation issues, fix the data.

Rules:
- For format errors (non-numeric grades): try to extract or convert to a numeric value:
  - "85/100" -> "85"
  - "B+" -> "87", "A-" -> "92", "C" -> "75" (standard grade scale)
  - "Absent" or "absent" -> "0"
  - "Excused" or "N/A" -> "" (empty = skip)
  - "85%" -> "85"
- For missing students: suggest the closest matching name from the roster if possible
- For invalid grades (negative or over max): clamp to valid range
- For each fix, explain what you changed and why

Respond in this exact JSON format:
{"fixes": [{"row": <int>, "col": <int>, "old": "<str>", "new": "<str>", "reason": "<str>"}, ...]}"""


@router.post("/fix", response_model=FixResult)
async def fix_gradebook(
    request: FixRequest,
    user_id: uuid.UUID = Depends(require_instructor),
    claude: ClaudeClient = Depends(get_claude),
) -> FixResult:
    """Use Claude to fix validation issues in the spreadsheet data."""
    import json

    issues_desc = "\n".join(
        f"Row {i.row}, Col {i.col}: {i.type} — current='{i.current}', expected='{i.expected}', hint='{i.suggestion}'"
        for i in request.issues
    )

    fix_prompt = (
        f"Spreadsheet headers: {request.source_data.headers}\n\n"
        f"Issues to fix:\n{issues_desc}\n\n"
        f"Relevant rows:\n"
    )
    issue_rows = sorted(set(i.row for i in request.issues))
    for row_idx in issue_rows[:20]:
        if row_idx < len(request.source_data.rows):
            fix_prompt += f"  Row {row_idx}: {request.source_data.rows[row_idx]}\n"

    fix_prompt += "\nProvide fixes for these issues."

    fix_text = await claude.chat(
        system_prompt=FIX_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": fix_prompt}],
        max_tokens=800,
        temperature=0.1,
    )

    # Parse fixes
    changes: list[dict[str, Any]] = []
    fixed_rows = [list(row) for row in request.source_data.rows]  # Deep copy

    try:
        json_start = fix_text.find("{")
        json_end = fix_text.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            fix_json = json.loads(fix_text[json_start:json_end])
            for fix in fix_json.get("fixes", []):
                row = fix["row"]
                col = fix["col"]
                new_val = str(fix["new"])
                if row < len(fixed_rows) and col < len(fixed_rows[row]):
                    old_val = fixed_rows[row][col]
                    fixed_rows[row][col] = new_val
                    changes.append(
                        {
                            "row": row,
                            "col": col,
                            "old": old_val,
                            "new": new_val,
                            "reason": fix.get("reason", ""),
                        }
                    )
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Failed to parse fix response", error=str(e))

    return FixResult(
        fixed_data=SpreadsheetData(
            title=request.source_data.title,
            headers=request.source_data.headers,
            rows=fixed_rows,
        ),
        changes=changes,
    )


# ── Download fixed spreadsheet as Excel ──


@router.post("/download-excel")
async def download_fixed_excel(
    source_data: SpreadsheetData,
    _user_id: uuid.UUID = Depends(require_instructor),
) -> StreamingResponse:
    """Generate an Excel file from the current (fixed) spreadsheet data."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = source_data.title or "Gradebook"

    ws.append(source_data.headers)
    for row in source_data.rows:
        ws.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"{(source_data.title or 'Gradebook').replace(' ', '_')}.xlsx"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
