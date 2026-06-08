"""Transport-level tests for the Canvas LMS adapter.

These exercise the *real* httpx stack (URL building, Bearer auth header, query
params, and Link-header pagination) by injecting an ``httpx.MockTransport`` into
the adapter's inline ``httpx.AsyncClient`` calls. Only Canvas's HTTP responses
are faked — every line of ``canvas.py`` runs unmodified.

Fixture JSON shapes are copied from the official Canvas REST API docs
(developerdocs.instructure.com) so the mocks match reality:
- Enrollment nested ``user`` has NO email/login_id  → validates the two-phase
  profile fetch in ``get_enrollments``.
- File metadata uses the hyphenated ``content-type`` key (a Canvas quirk).
- ModuleItem uses ``content_id`` (files) and ``page_url`` (pages).
- User Profile carries ``primary_email``.
"""

import httpx
import pytest

from docere.integrations.lms import canvas as canvas_mod
from docere.integrations.lms.canvas import CanvasAdapter

BASE_URL = "https://canvas.test"
API = f"{BASE_URL}/api/v1"
TOKEN = "test-token"
COURSE_ID = "123"


# ── Real (minimal) PDF builder ──────────────────────────────────────────────


def _build_minimal_pdf(text: str) -> bytes:
    """Assemble a valid single-page PDF with extractable text.

    Byte offsets in the xref table are computed so pypdf parses it without
    falling back to xref reconstruction.
    """
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    ]
    stream = b"BT /F1 24 Tf 72 700 Td (" + text.encode("latin-1") + b") Tj ET"
    objects.append(
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    pdf = b"%PDF-1.4\n"
    offsets: list[int] = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n"

    xref_pos = len(pdf)
    size = len(objects) + 1
    pdf += b"xref\n0 " + str(size).encode() + b"\n"
    pdf += b"0000000000 65535 f \n"
    for off in offsets:
        pdf += ("%010d 00000 n \n" % off).encode()
    pdf += b"trailer\n<< /Size " + str(size).encode() + b" /Root 1 0 R >>\n"
    pdf += b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF"
    return pdf


PDF_TEXT = "Lecture 4: Merge Sort"
PDF_BYTES = _build_minimal_pdf(PDF_TEXT)


# ── Canvas fixture data (shapes from official docs) ─────────────────────────

COURSE_JSON = {
    "id": 123,
    "name": "Algorithms",
    "course_code": "CS201",
    "syllabus_body": "<p>syllabus html</p>",
    "term": {"id": 34, "name": "Fall 2026", "start_at": "2026-08-01T00:00:00Z"},
}

ASSIGNMENTS_JSON = [
    {
        "id": 4,
        "name": "Problem Set 1",
        "description": "<p>Do the following</p>",
        "due_at": "2026-09-01T23:59:00Z",
        "points_possible": 12.0,
        "submission_types": ["online_upload"],
    },
    {
        "id": 5,
        "name": "Problem Set 2",
        "description": None,
        "due_at": None,
        "points_possible": 20.0,
        "submission_types": [],
    },
]

SUBMISSIONS_JSON = [
    {
        "id": 134,
        "assignment_id": 4,
        "user_id": 10,
        "score": 11.0,
        "grade": "A-",
        "submitted_at": "2026-09-01T01:00:00Z",
        "graded_at": "2026-09-02T03:05:34Z",
        "workflow_state": "graded",
    }
]

# Enrollments split across two pages to exercise Link-header pagination.
# Note: nested `user` has NO email — must be fetched via /users/:id/profile.
ENROLLMENTS_PAGE_1 = [
    {
        "id": 1,
        "user_id": 10,
        "course_id": 123,
        "type": "StudentEnrollment",
        "role": "StudentEnrollment",
        "user": {"id": 10, "name": "Alice Student", "short_name": "Alice"},
    },
    {
        "id": 2,
        "user_id": 11,
        "course_id": 123,
        "type": "TeacherEnrollment",
        "role": "TeacherEnrollment",
        "user": {"id": 11, "name": "Bob Teacher", "short_name": "Bob"},
    },
]
ENROLLMENTS_PAGE_2 = [
    {
        # Custom role name — `role` is "Lab TA" but `type` is canonical.
        "id": 3,
        "user_id": 12,
        "course_id": 123,
        "type": "TaEnrollment",
        "role": "Lab TA",
        "user": {"id": 12, "name": "Carol TA", "short_name": "Carol"},
    },
    {
        # Duplicate of Alice (same user_id) — must NOT cause a 2nd profile fetch.
        "id": 4,
        "user_id": 10,
        "course_id": 123,
        "type": "StudentEnrollment",
        "role": "StudentEnrollment",
        "user": {"id": 10, "name": "Alice Student", "short_name": "Alice"},
    },
]

PROFILES = {
    "10": {"id": 10, "name": "Alice Student", "primary_email": "alice@test.edu"},
    "11": {"id": 11, "name": "Bob Teacher", "primary_email": "bob@test.edu"},
    # 12 intentionally errors (handled below) → email None (graceful degradation)
}

USER_COURSES_JSON = [
    {"id": 123, "name": "Algorithms", "course_code": "CS201"},
    {"id": 456, "name": "Data Structures", "course_code": "CS101"},
]

MODULES_JSON = [
    {
        "id": 201,
        "name": "Week 1",
        "items": [
            {"id": 101, "type": "File", "title": "Syllabus PDF",
             "content_id": 777, "html_url": f"{BASE_URL}/courses/123/files/777"},
            {"id": 102, "type": "Page", "title": "Welcome",
             "page_url": "welcome", "html_url": f"{BASE_URL}/courses/123/pages/welcome"},
            {"id": 103, "type": "SubHeader", "title": "Readings"},
            {"id": 104, "type": "Assignment", "title": "Problem Set 1",
             "content_id": 4, "html_url": f"{BASE_URL}/courses/123/assignments/4"},
        ],
    },
    {
        "id": 202,
        "name": "Week 2",
        "items": [
            {"id": 105, "type": "File", "title": "Notes (txt)",
             "content_id": 778, "html_url": f"{BASE_URL}/courses/123/files/778"},
            # Duplicate of file 777 in another module → deduped away.
            {"id": 106, "type": "File", "title": "Syllabus again",
             "content_id": 777, "html_url": f"{BASE_URL}/courses/123/files/777"},
        ],
    },
]

FILES = {
    "777": {
        "id": 777, "display_name": "syllabus.pdf", "filename": "syllabus.pdf",
        "content-type": "application/pdf",
        "url": "https://files.canvas.test/files/777/download?download_frd=1",
        "size": len(PDF_BYTES),
    },
    "778": {
        "id": 778, "display_name": "notes.txt", "filename": "notes.txt",
        "content-type": "text/plain",
        "url": "https://files.canvas.test/files/778/download?download_frd=1",
        "size": 10,
    },
}

PAGE_WELCOME = {
    "page_id": 1, "url": "welcome", "title": "Welcome",
    "body": "<p>Welcome to the course</p>", "published": True,
}

EFFECTIVE_DUE_DATES = {
    "4": {"10": {"due_at": "2026-09-03T23:59:00Z", "grading_period_id": None}}
}

ASSIGNMENT_GROUPS = [
    {
        "id": 1, "name": "Homework", "position": 1,
        "assignments": [
            {"id": 4, "name": "Problem Set 1", "points_possible": 12.0},
            {"id": 5, "name": "Problem Set 2", "points_possible": 20.0},
        ],
    },
    {
        "id": 2, "name": "Exams", "position": 2,
        "assignments": [{"id": 6, "name": "Midterm", "points_possible": 100.0}],
    },
]


# ── MockTransport router + fixture ──────────────────────────────────────────


class CanvasMock:
    """Holds the adapter plus a log of every request the handler saw."""

    def __init__(self, adapter: CanvasAdapter):
        self.adapter = adapter
        self.requests: list[httpx.Request] = []

    def paths(self, method: str | None = None) -> list[str]:
        return [
            r.url.path for r in self.requests
            if method is None or r.method == method
        ]


def _make_handler(mock: CanvasMock):
    def handler(request: httpx.Request) -> httpx.Response:
        mock.requests.append(request)
        path = request.url.path
        method = request.method
        params = request.url.params

        # ── PDF / file downloads (separate host) ──
        if path.endswith("/download"):
            if path.endswith("/777/download"):
                return httpx.Response(200, content=PDF_BYTES)
            return httpx.Response(200, content=b"plain text body")

        if method == "GET":
            # GET /courses/:id  (single course)
            if path == "/api/v1/courses/123":
                return httpx.Response(200, json=COURSE_JSON)
            if path == "/api/v1/courses/123/assignments":
                return httpx.Response(200, json=ASSIGNMENTS_JSON)
            if path == "/api/v1/courses/123/assignments/4/submissions":
                return httpx.Response(200, json=SUBMISSIONS_JSON)
            if path == "/api/v1/courses/123/students/submissions":
                return httpx.Response(200, json=SUBMISSIONS_JSON)
            if path == "/api/v1/courses/123/enrollments":
                if params.get("page") == "2":
                    return httpx.Response(200, json=ENROLLMENTS_PAGE_2)
                next_url = f"{API}/courses/123/enrollments?page=2"
                return httpx.Response(
                    200, json=ENROLLMENTS_PAGE_1,
                    headers={"Link": f'<{next_url}>; rel="next"'},
                )
            if path.startswith("/api/v1/users/") and path.endswith("/profile"):
                uid = path.split("/")[4]
                if uid in PROFILES:
                    return httpx.Response(200, json=PROFILES[uid])
                return httpx.Response(500, json={"errors": ["boom"]})
            if path == "/api/v1/users/10/courses":
                return httpx.Response(200, json=USER_COURSES_JSON)
            if path == "/api/v1/courses/123/modules":
                return httpx.Response(200, json=MODULES_JSON)
            if path.startswith("/api/v1/courses/123/files/"):
                fid = path.split("/")[-1]
                return httpx.Response(200, json=FILES[fid])
            if path.startswith("/api/v1/courses/123/pages/"):
                return httpx.Response(200, json=PAGE_WELCOME)
            if path == "/api/v1/courses/123/effective_due_dates":
                return httpx.Response(200, json=EFFECTIVE_DUE_DATES)
            if path == "/api/v1/courses/123/assignment_groups":
                return httpx.Response(200, json=ASSIGNMENT_GROUPS)

        if method == "PUT" and "/submissions/" in path:
            return httpx.Response(200, json={"id": 1, "grade": "95"})

        if method == "POST" and path.endswith("/discussion_topics"):
            return httpx.Response(200, json={
                "id": 99, "title": "T", "message": "m",
                "html_url": f"{BASE_URL}/courses/123/discussion_topics/99",
                "is_announcement": True, "published": True,
            })

        return httpx.Response(404, json={"errors": [f"unrouted {method} {path}"]})

    return handler


@pytest.fixture
def canvas(monkeypatch) -> CanvasMock:
    adapter = CanvasAdapter(BASE_URL, TOKEN)
    mock = CanvasMock(adapter)
    transport = httpx.MockTransport(_make_handler(mock))
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs.setdefault("transport", transport)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(canvas_mod.httpx, "AsyncClient", client_factory)
    return mock


# ── Plumbing: auth header, params, pagination ───────────────────────────────


async def test_bearer_auth_header_sent_on_every_request(canvas):
    await canvas.adapter.get_course(COURSE_ID)
    assert canvas.requests, "no requests captured"
    for req in canvas.requests:
        assert req.headers["Authorization"] == f"Bearer {TOKEN}"


async def test_get_course_sends_include_params_and_parses_term(canvas):
    course = await canvas.adapter.get_course(COURSE_ID)
    assert course.term == "Fall 2026"
    assert course.external_id == "123"
    assert course.course_code == "CS201"
    # include[]=syllabus_body,term must be on the wire
    includes = canvas.requests[0].url.params.get_list("include[]")
    assert set(includes) == {"syllabus_body", "term"}


async def test_pagination_follows_link_header(canvas):
    enrollments = await canvas.adapter.get_enrollments(COURSE_ID)
    # 2 raw rows page1 + 2 rows page2 = 4 enrollment rows
    assert len(enrollments) == 4
    enrollment_paths = [
        r.url for r in canvas.requests if r.url.path.endswith("/enrollments")
    ]
    assert len(enrollment_paths) == 2
    assert str(enrollment_paths[1]).endswith("page=2")


# ── get_enrollments: two-phase fetch, dedup, type-not-role ──────────────────


async def test_enrollments_roles_use_type_not_custom_role(canvas):
    enrollments = await canvas.adapter.get_enrollments(COURSE_ID)
    by_user = {e.user_id: e for e in enrollments}
    assert by_user["10"].role == "student"
    assert by_user["11"].role == "teacher"
    # Carol's `role` is the custom "Lab TA" — must still map to ta via `type`.
    assert by_user["12"].role == "ta"


async def test_enrollments_emails_from_profile_endpoint(canvas):
    enrollments = await canvas.adapter.get_enrollments(COURSE_ID)
    by_user = {e.user_id: e for e in enrollments}
    assert by_user["10"].email == "alice@test.edu"
    assert by_user["11"].email == "bob@test.edu"
    # Profile fetch for user 12 errors → graceful degradation to None.
    assert by_user["12"].email is None


async def test_enrollments_dedups_profile_fetches(canvas):
    await canvas.adapter.get_enrollments(COURSE_ID)
    profile_calls = [p for p in canvas.paths("GET") if p.endswith("/profile")]
    # 3 unique users (10, 11, 12) despite Alice appearing in 2 enrollment rows.
    assert len(profile_calls) == 3


# ── get_assignments / get_submissions ───────────────────────────────────────


async def test_get_assignments_params_and_mapping(canvas):
    assignments = await canvas.adapter.get_assignments(COURSE_ID)
    assert [a.external_id for a in assignments] == ["4", "5"]
    assert assignments[0].assignment_type == "online_upload"
    # Empty submission_types → assignment_type None (no IndexError).
    assert assignments[1].assignment_type is None
    params = canvas.requests[0].url.params
    assert params.get_list("include[]") == ["submission"]
    assert params.get("order_by") == "due_at"


async def test_get_submissions_for_assignment_uses_scoped_path(canvas):
    subs = await canvas.adapter.get_submissions(COURSE_ID, assignment_id="4")
    assert len(subs) == 1
    assert subs[0].student_id == "10"
    assert subs[0].score == 11.0
    assert canvas.paths("GET") == ["/api/v1/courses/123/assignments/4/submissions"]


async def test_get_submissions_course_wide_path(canvas):
    await canvas.adapter.get_submissions(COURSE_ID)
    assert canvas.paths("GET") == ["/api/v1/courses/123/students/submissions"]


async def test_get_user_courses(canvas):
    courses = await canvas.adapter.get_user_courses("10")
    assert {c.external_id for c in courses} == {"123", "456"}


# ── get_course_materials: modules walk, dispatch, dedup, extraction ─────────


async def test_course_materials_dispatch_and_dedup(canvas):
    materials = await canvas.adapter.get_course_materials(COURSE_ID)
    by_id = {m.external_id: m for m in materials}
    # SubHeader skipped; duplicate file 777 deduped → File(777), Page, Assignment, File(778)
    assert len(materials) == 4
    assert by_id["777"].material_type == "file"
    assert by_id["welcome"].material_type == "page"
    # Metadata-only items key off the module item id (104), not content_id.
    assert by_id["104"].material_type == "assignment"


async def test_course_materials_pdf_extracted_with_hash(canvas):
    materials = await canvas.adapter.get_course_materials(COURSE_ID)
    pdf = next(m for m in materials if m.external_id == "777")
    assert pdf.content is not None
    assert "Merge Sort" in pdf.content
    assert pdf.content_hash is not None
    assert len(pdf.content_hash) == 64


async def test_course_materials_non_pdf_has_no_content(canvas):
    materials = await canvas.adapter.get_course_materials(COURSE_ID)
    txt = next(m for m in materials if m.external_id == "778")
    assert txt.content is None
    assert txt.content_hash is None


async def test_course_materials_page_body_extracted(canvas):
    materials = await canvas.adapter.get_course_materials(COURSE_ID)
    page = next(m for m in materials if m.external_id == "welcome")
    assert page.content == "<p>Welcome to the course</p>"
    assert len(page.content_hash) == 64


async def test_course_materials_metadata_only_item_has_no_content(canvas):
    materials = await canvas.adapter.get_course_materials(COURSE_ID)
    assignment = next(m for m in materials if m.external_id == "104")
    assert assignment.content is None


# ── PDF size guard + graceful degradation ───────────────────────────────────


async def test_pdf_size_limit_rejects_oversize_file(canvas, monkeypatch):
    monkeypatch.setattr(canvas_mod, "MAX_PDF_SIZE", 10)
    content = await canvas.adapter._download_and_extract_pdf(
        FILES["777"]["url"]
    )
    assert content is None


async def test_file_metadata_failure_degrades_gracefully(canvas):
    # Unknown file id → handler returns 404 inside files/, _get raises,
    # _extract_file_content swallows it and returns (None, None).
    content, content_hash = await canvas.adapter._extract_file_content(
        COURSE_ID, "99999"
    )
    assert content is None and content_hash is None


# ── Read paths: effective due dates, grade items ────────────────────────────


async def test_get_effective_due_dates(canvas):
    data = await canvas.adapter.get_effective_due_dates(COURSE_ID)
    assert data["4"]["10"]["due_at"] == "2026-09-03T23:59:00Z"


async def test_get_grade_items_flattens_groups_with_category(canvas):
    items = await canvas.adapter.get_grade_items(COURSE_ID)
    assert {i["id"] for i in items} == {"4", "5", "6"}
    by_id = {i["id"]: i for i in items}
    assert by_id["4"]["category"] == "Homework"
    assert by_id["6"]["category"] == "Exams"
    assert by_id["6"]["grade_max"] == 100.0


# ── Write paths: save_grade, post_announcement ──────────────────────────────


async def test_save_grade_sends_posted_grade_and_comment(canvas):
    result = await canvas.adapter.save_grade(
        COURSE_ID, "4", "10", 95.0, feedback="Nice work"
    )
    assert result == {"success": True}
    put_req = next(r for r in canvas.requests if r.method == "PUT")
    import json
    body = json.loads(put_req.content)
    assert body["submission"]["posted_grade"] == "95.0"
    assert body["comment"]["text_comment"] == "Nice work"


async def test_post_announcement_returns_id_and_url(canvas):
    result = await canvas.adapter.post_announcement(
        COURSE_ID, "Heads up", "Class cancelled"
    )
    assert result["id"] == "99"
    assert result["url"].endswith("/discussion_topics/99")
    post_req = next(r for r in canvas.requests if r.method == "POST")
    import json
    body = json.loads(post_req.content)
    assert body["is_announcement"] is True


# ── Error propagation ───────────────────────────────────────────────────────


async def test_non_2xx_raises(canvas):
    # /courses/999 is unrouted → 404 → raise_for_status propagates.
    with pytest.raises(httpx.HTTPStatusError):
        await canvas.adapter.get_course("999")
