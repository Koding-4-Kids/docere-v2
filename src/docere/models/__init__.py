"""SQLAlchemy ORM models - import all for Alembic auto-detection."""

from docere.models.alert import Alert  # noqa: F401
from docere.models.analytics import LearningAnalyticsEvent  # noqa: F401
from docere.models.base import Base  # noqa: F401
from docere.models.calendar import (  # noqa: F401
    InstructorCalendarToken,
    MeetingRequest,
    OfficeHours,
)
from docere.models.conversation import Conversation, Message  # noqa: F401
from docere.models.course import (  # noqa: F401
    Assignment,
    Course,
    CourseMaterial,
    Enrollment,
    Submission,
)
from docere.models.flashcard import CardReview, FlashcardCard, FlashcardDeck  # noqa: F401
from docere.models.lti_platform import LTIPlatform  # noqa: F401
from docere.models.memory import ConceptMastery, MemoryRecord, StudentProfile  # noqa: F401
from docere.models.research import ResearchEvent, StudyConfig  # noqa: F401
from docere.models.strategy import Strategy, StrategyScore  # noqa: F401
from docere.models.user import User  # noqa: F401
from docere.models.verification import InteractionScore  # noqa: F401
