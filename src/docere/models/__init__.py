"""SQLAlchemy ORM models - import all for Alembic auto-detection."""

from docere.models.base import Base  # noqa: F401
from docere.models.user import User  # noqa: F401
from docere.models.course import Course, Enrollment, Assignment, Submission, CourseMaterial  # noqa: F401
from docere.models.conversation import Conversation, Message  # noqa: F401
from docere.models.memory import MemoryRecord, StudentProfile, ConceptMastery  # noqa: F401
from docere.models.verification import InteractionScore  # noqa: F401
from docere.models.strategy import Strategy, StrategyScore  # noqa: F401
from docere.models.alert import Alert  # noqa: F401
from docere.models.analytics import LearningAnalyticsEvent  # noqa: F401
from docere.models.research import StudyConfig, ResearchEvent  # noqa: F401
from docere.models.lti_platform import LTIPlatform  # noqa: F401
