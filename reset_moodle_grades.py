"""Reset all Moodle grades to 0 for testing the gradebook sync."""

import asyncio
import httpx
import os

BASE_URL = os.environ.get("MOODLE_BASE_URL", "http://localhost:8080").rstrip("/")
TOKEN = os.environ.get("MOODLE_API_TOKEN", "")

# Update this to your course ID in Moodle
COURSE_ID = os.environ.get("MOODLE_COURSE_ID", "2")


async def moodle_call(function: str, params: dict | None = None):
    request_params = {
        "wstoken": TOKEN,
        "wsfunction": function,
        "moodlewsrestformat": "json",
        **(params or {}),
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/webservice/rest/server.php",
            params=request_params,
        )
        resp.raise_for_status()
        return resp.json()


async def main():
    if not TOKEN:
        print("Set MOODLE_API_TOKEN env var first")
        return

    print(f"Moodle: {BASE_URL}")
    print(f"Course: {COURSE_ID}\n")

    # 1. Get all assignments
    data = await moodle_call(
        "mod_assign_get_assignments",
        {"courseids[0]": COURSE_ID},
    )
    assignments = []
    for course_data in data.get("courses", []):
        for a in course_data.get("assignments", []):
            assignments.append({
                "id": a["id"],
                "name": a.get("name", ""),
                "grade_max": a.get("grade", 100),
            })

    print(f"Found {len(assignments)} assignments:")
    for a in assignments:
        print(f"  - {a['name']} (id={a['id']}, max={a['grade_max']})")

    # 2. Get enrolled students
    users = await moodle_call(
        "core_enrol_get_enrolled_users",
        {"courseid": COURSE_ID},
    )
    students = [
        u for u in users
        if isinstance(u, dict)
        and any(r.get("shortname") == "student" for r in u.get("roles", []))
    ]

    print(f"\nFound {len(students)} students:")
    for s in students:
        print(f"  - {s.get('fullname', '?')} (id={s['id']})")

    # 3. Set every grade to 0
    print(f"\nSetting all grades to 0...")
    total = 0
    errors = 0

    for a in assignments:
        for s in students:
            try:
                result = await moodle_call("mod_assign_save_grade", {
                    "assignmentid": a["id"],
                    "userid": s["id"],
                    "grade": 0,
                    "attemptnumber": -1,
                    "addattempt": 1,
                    "workflowstate": "graded",
                    "applytoall": 0,
                })
                if isinstance(result, dict) and result.get("exception"):
                    print(f"  FAIL: {s.get('fullname')} / {a['name']} — {result.get('message')}")
                    errors += 1
                else:
                    total += 1
            except Exception as e:
                print(f"  ERROR: {s.get('fullname')} / {a['name']} — {e}")
                errors += 1

    print(f"\nDone! Set {total} grades to 0. ({errors} errors)")


if __name__ == "__main__":
    asyncio.run(main())
