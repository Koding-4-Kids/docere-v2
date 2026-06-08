"""LTI 1.3 business logic: claim extraction, user/course upsert, adapter creation."""

from dataclasses import dataclass

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.core.improvement.experiment_runner import ExperimentRunner
from docere.integrations.lms.base import LMSAdapter
from docere.integrations.lms.canvas import CanvasAdapter
from docere.integrations.lms.moodle import MoodleAdapter
from docere.models.course import Course, Enrollment
from docere.models.lti_platform import LTIPlatform
from docere.models.user import User

logger = structlog.get_logger()

# LTI 1.3 claim URIs
LTI_CLAIM_MESSAGE_TYPE = "https://purl.imsglobal.org/spec/lti/claim/message_type"
LTI_CLAIM_ROLES = "https://purl.imsglobal.org/spec/lti/claim/roles"
LTI_CLAIM_CONTEXT = "https://purl.imsglobal.org/spec/lti/claim/context"
LTI_CLAIM_LIS = "https://purl.imsglobal.org/spec/lti/claim/lis"
LTI_CLAIM_CUSTOM = "https://purl.imsglobal.org/spec/lti/claim/custom"


@dataclass
class LTILaunchData:
    """Normalized user/course/role data extracted from LTI JWT claims."""

    # User info
    external_user_id: str
    email: str | None
    name: str
    role: str  # "student", "instructor", "ta"

    # Course info
    external_course_id: str | None
    course_name: str | None

    # Platform reference
    platform_id: str


def extract_lti_claims(claims: dict, platform: LTIPlatform) -> LTILaunchData:
    """Extract normalized user/course data from LTI 1.3 JWT claims.

    Handles differences between Canvas and Moodle claim structures.
    """
    # User identity — 'sub' is the LTI standard user ID
    external_user_id = claims.get("sub", "")

    # Name: try standard fields, then Canvas/Moodle specifics
    name = claims.get("name", "")
    if not name:
        given = claims.get("given_name", "")
        family = claims.get("family_name", "")
        name = f"{given} {family}".strip() or "Unknown"

    email = claims.get("email")

    # Role detection from LTI roles claim
    roles = claims.get(LTI_CLAIM_ROLES, [])
    role = _parse_lti_role(roles)

    # Course context
    context = claims.get(LTI_CLAIM_CONTEXT, {})
    external_course_id = None
    course_name = None

    if context:
        # Canvas uses 'id' in context, Moodle may use label
        external_course_id = context.get("id")
        course_name = context.get("title") or context.get("label")

        # Canvas also passes course ID in custom claims
        if not external_course_id and platform.platform_type == "canvas":
            custom = claims.get(LTI_CLAIM_CUSTOM, {})
            external_course_id = custom.get("canvas_course_id")

    return LTILaunchData(
        external_user_id=external_user_id,
        email=email,
        name=name,
        role=role,
        external_course_id=external_course_id,
        course_name=course_name,
        platform_id=str(platform.id),
    )


def _parse_lti_role(roles: list[str]) -> str:
    """Map LTI role URIs to our simple role names."""
    for role_uri in roles:
        role_lower = role_uri.lower()
        if "instructor" in role_lower or "faculty" in role_lower:
            return "instructor"
        if "teachingassistant" in role_lower:
            return "ta"
        if "administrator" in role_lower:
            return "admin"
    # Default to student if no instructor/admin role found
    return "student"


async def upsert_lti_user(
    db: AsyncSession,
    lti_data: LTILaunchData,
    platform: LTIPlatform,
) -> User:
    """Create or update a user from LTI launch claims.

    Uses (external_lms_id, lms_platform) as the unique key,
    where lms_platform = str(platform.id) for multi-tenant uniqueness.
    """
    lms_platform = str(platform.id)

    result = await db.execute(
        select(User).where(
            User.external_lms_id == lti_data.external_user_id,
            User.lms_platform == lms_platform,
        )
    )
    user = result.scalar_one_or_none()

    if user:
        # Update name/email if changed
        user.name = lti_data.name
        if lti_data.email:
            user.email = lti_data.email
        user.role = lti_data.role
    else:
        user = User(
            external_lms_id=lti_data.external_user_id,
            lms_platform=lms_platform,
            name=lti_data.name,
            email=lti_data.email,
            role=lti_data.role,
        )
        db.add(user)
        await db.flush()

    logger.info(
        "LTI user upserted",
        user_id=str(user.id),
        external_id=lti_data.external_user_id,
        role=lti_data.role,
    )
    return user


async def handle_lti_course(
    db: AsyncSession,
    lti_data: LTILaunchData,
    platform: LTIPlatform,
    user: User,
) -> tuple[Course | None, bool]:
    """Find or create a course from LTI launch context.

    Returns (course, is_new) — is_new=True means a full sync should be enqueued.
    """
    if not lti_data.external_course_id:
        return None, False

    lms_platform = str(platform.id)

    result = await db.execute(
        select(Course).where(
            Course.external_lms_id == lti_data.external_course_id,
            Course.lms_platform == lms_platform,
        )
    )
    course = result.scalar_one_or_none()

    if course:
        return course, False

    # Create new course stub — full data comes from background sync
    course = Course(
        external_lms_id=lti_data.external_course_id,
        lms_platform=lms_platform,
        name=lti_data.course_name or f"Course {lti_data.external_course_id}",
        lms_sync_enabled=True,
    )
    # If launching user is instructor, set them as course instructor
    if lti_data.role == "instructor":
        course.instructor_id = user.id
    db.add(course)
    await db.flush()

    logger.info(
        "New course created from LTI launch",
        course_id=str(course.id),
        external_id=lti_data.external_course_id,
    )
    return course, True


async def ensure_enrollment(
    db: AsyncSession,
    user: User,
    course: Course,
    lti_role: str = "student",
) -> Enrollment:
    """Create enrollment if it doesn't exist, assign study group via ExperimentRunner."""
    result = await db.execute(
        select(Enrollment).where(
            Enrollment.user_id == user.id,
            Enrollment.course_id == course.id,
        )
    )
    enrollment = result.scalar_one_or_none()

    if enrollment:
        return enrollment

    enrollment = Enrollment(
        user_id=user.id,
        course_id=course.id,
        lms_role=lti_role,
    )
    db.add(enrollment)
    await db.flush()

    # Assign study group for A/B testing
    runner = ExperimentRunner(db)
    group = await runner.assign_student_group(
        student_id=str(user.id),
        course_id=str(course.id),
    )
    if not group:
        # No active study — default to treatment_full (all features enabled)
        enrollment.study_group = "treatment_full"
        await db.flush()

    logger.info(
        "Enrollment created",
        user_id=str(user.id),
        course_id=str(course.id),
        study_group=enrollment.study_group,
    )
    return enrollment


async def sync_user_enrollments(
    db: AsyncSession,
    user: User,
    lms_adapter: LMSAdapter,
    platform: LTIPlatform,
) -> int:
    """Discover all courses the user is enrolled in via the LMS and ensure
    local Course + Enrollment records exist for each.

    Called during LTI launch so that the user sees all their courses
    immediately, not just the one they launched from.

    Returns the number of new enrollments created.
    """
    if not user.external_lms_id:
        return 0

    lms_platform = str(platform.id)

    try:
        lms_courses = await lms_adapter.get_user_courses(user.external_lms_id)
    except Exception:
        logger.warning(
            "Failed to fetch user courses from LMS",
            user_id=str(user.id),
            external_id=user.external_lms_id,
        )
        return 0

    created = 0
    for lms_course in lms_courses:
        # Find or create the course
        result = await db.execute(
            select(Course).where(
                Course.external_lms_id == lms_course.external_id,
                Course.lms_platform == lms_platform,
            )
        )
        course = result.scalar_one_or_none()

        if not course:
            course = Course(
                external_lms_id=lms_course.external_id,
                lms_platform=lms_platform,
                name=lms_course.name,
                course_code=lms_course.course_code,
                lms_sync_enabled=True,
            )
            db.add(course)
            await db.flush()

        # Ensure enrollment exists
        result = await db.execute(
            select(Enrollment).where(
                Enrollment.user_id == user.id,
                Enrollment.course_id == course.id,
            )
        )
        if not result.scalar_one_or_none():
            db.add(
                Enrollment(
                    user_id=user.id,
                    course_id=course.id,
                    lms_role="student",
                )
            )
            created += 1

    if created:
        await db.flush()
        logger.info(
            "Cross-course enrollments synced",
            user_id=str(user.id),
            new_enrollments=created,
            total_courses=len(lms_courses),
        )

    return created


def create_adapter(platform: LTIPlatform) -> LMSAdapter:
    """Instantiate the correct LMS adapter with per-platform credentials."""
    if platform.platform_type == "canvas":
        return CanvasAdapter(
            base_url=platform.api_base_url,
            api_token=platform.api_token,
        )
    elif platform.platform_type == "moodle":
        return MoodleAdapter(
            base_url=platform.api_base_url,
            api_token=platform.api_token,
        )
    else:
        raise ValueError(f"Unknown platform type: {platform.platform_type}")
