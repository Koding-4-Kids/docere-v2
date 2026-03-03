"""Tests for endpoint response schemas and model validation.

These test the Pydantic models and response shapes without needing
a real database - just verifying the schemas are correct.
"""

import uuid
from datetime import UTC, datetime

import pytest


class TestInstructorSchemas:
    """Verify instructor endpoint response models."""

    def test_alert_response_model(self):
        from docere.api.instructor import AlertResponse

        alert = AlertResponse(
            id=str(uuid.uuid4()),
            alert_type="struggling_student",
            severity="high",
            title="Student struggling with recursion",
            message="This student has high confusion scores.",
            is_read=False,
            is_resolved=False,
            course_id=str(uuid.uuid4()),
            created_at=datetime.now(UTC).isoformat(),
        )
        assert alert.severity == "high"
        assert alert.is_read is False

    def test_dashboard_response_model(self):
        from docere.api.instructor import DashboardResponse

        dashboard = DashboardResponse(
            course_id=str(uuid.uuid4()),
            student_count=25,
            avg_grade=78.5,
            avg_confusion=0.35,
            engagement_breakdown={"high": 10, "medium": 8, "low": 5, "inactive": 2},
            total_interactions=450,
            top_struggling_concepts=[
                {"concept": "recursion", "avg_mastery": 0.3, "times_struggled": 15, "student_count": 8},
            ],
        )
        assert dashboard.student_count == 25
        assert dashboard.engagement_breakdown["high"] == 10

    def test_at_risk_response_model(self):
        from docere.api.instructor import AtRiskStudentResponse

        student = AtRiskStudentResponse(
            student_id=str(uuid.uuid4()),
            student_name="Test Student",
            engagement_level="low",
            avg_confusion=0.72,
            current_grade=55.0,
            risk_reasons=["Low engagement (low)", "High confusion (72.0%)", "Low grade (55%)"],
        )
        assert len(student.risk_reasons) == 3
        assert student.engagement_level == "low"

    def test_pattern_item_model(self):
        from docere.api.instructor import PatternItem

        pattern = PatternItem(
            concept="recursion",
            avg_mastery=0.35,
            mastery_label="struggling",
            times_struggled=20,
            student_count=12,
            times_practiced=45,
        )
        assert pattern.mastery_label == "struggling"

    def test_update_alert_request_all_none(self):
        from docere.api.instructor import UpdateAlertRequest

        req = UpdateAlertRequest()
        assert req.is_read is None
        assert req.is_resolved is None


class TestStudentSchemas:
    """Verify student endpoint response models."""

    def test_student_list_item(self):
        from docere.api.students import StudentListItem

        item = StudentListItem(
            student_id=str(uuid.uuid4()),
            name="Alice",
            engagement_level="high",
            avg_confusion=0.2,
            current_grade=92.0,
            total_interactions=30,
        )
        assert item.name == "Alice"

    def test_student_profile_response(self):
        from docere.api.students import StudentProfileResponse

        profile = StudentProfileResponse(
            student_id=str(uuid.uuid4()),
            name="Bob",
            engagement_level="medium",
            avg_confusion=0.4,
            avg_interaction_score=0.7,
            top_concepts=[],
            memory_counts={"question": 5, "struggle": 3, "breakthrough": 1},
        )
        assert profile.memory_counts["question"] == 5

    def test_interaction_item(self):
        from docere.api.students import InteractionItem

        item = InteractionItem(
            conversation_id=str(uuid.uuid4()),
            message_id=str(uuid.uuid4()),
            assistant_content="Here's an explanation...",
            created_at=datetime.now(UTC).isoformat(),
            helpfulness=0.8,
            clarity=0.7,
            composite_score=0.75,
        )
        assert item.composite_score == 0.75

    def test_memory_item(self):
        from docere.api.students import MemoryItem

        item = MemoryItem(
            id=str(uuid.uuid4()),
            memory_type="struggle",
            content="Had trouble with linked lists",
            concepts=["linked_lists", "pointers"],
            sentiment="frustrated",
            confusion_score=0.7,
            created_at=datetime.now(UTC).isoformat(),
        )
        assert item.memory_type == "struggle"
        assert len(item.concepts) == 2


class TestMemorySchemas:
    """Verify memory endpoint response models."""

    def test_my_memory_response(self):
        from docere.api.memory import MyMemoryResponse, MemorySummaryItem

        resp = MyMemoryResponse(
            total_memories=10,
            by_type={
                "question": [
                    MemorySummaryItem(
                        id=str(uuid.uuid4()),
                        memory_type="question",
                        content="How does quicksort work?",
                        created_at=datetime.now(UTC).isoformat(),
                    )
                ],
            },
        )
        assert resp.total_memories == 10
        assert len(resp.by_type["question"]) == 1

    def test_my_concept_item(self):
        from docere.api.memory import MyConceptItem

        item = MyConceptItem(
            concept="sorting",
            mastery_level=0.65,
            mastery_label="developing",
            times_practiced=10,
            times_struggled=3,
        )
        assert item.mastery_label == "developing"

    def test_my_stats_response(self):
        from docere.api.memory import MyStatsResponse

        stats = MyStatsResponse(
            total_interactions=50,
            total_messages=120,
            avg_confusion=0.3,
            engagement_level="high",
            memory_count=25,
            concept_count=8,
        )
        assert stats.total_interactions == 50


class TestAnalyticsSchemas:
    """Verify analytics endpoint response models."""

    def test_course_metrics_response(self):
        from docere.api.analytics import CourseMetricsResponse

        metrics = CourseMetricsResponse(
            course_id=str(uuid.uuid4()),
            student_count=30,
            engagement_breakdown={"high": 15, "medium": 10, "low": 5},
            avg_confusion=0.28,
            total_interactions=800,
        )
        assert metrics.student_count == 30

    def test_strategy_performance_item(self):
        from docere.api.analytics import StrategyPerformanceItem

        item = StrategyPerformanceItem(
            id=str(uuid.uuid4()),
            name="Socratic",
            strategy_type="questioning",
            total_uses=150,
            avg_score=0.72,
            success_rate=0.68,
            is_active=True,
            generation=2,
        )
        assert item.avg_score == 0.72

    def test_strategy_archive_item(self):
        from docere.api.analytics import StrategyArchiveItem

        item = StrategyArchiveItem(
            id=str(uuid.uuid4()),
            name="Scaffolding",
            description="Break problems into steps",
            strategy_type="structured",
            prompt_template="Guide the student step by step...",
            total_uses=80,
            is_active=True,
            is_baseline=False,
            generation=1,
            created_at=datetime.now(UTC).isoformat(),
        )
        assert item.strategy_type == "structured"

    def test_group_metrics(self):
        from docere.api.analytics import GroupMetrics

        gm = GroupMetrics(
            group_name="treatment",
            student_count=15,
            avg_interaction_score=0.73,
            avg_confusion=0.25,
            total_interactions=200,
            event_count=50,
        )
        assert gm.group_name == "treatment"

    def test_configure_study_request(self):
        from docere.api.analytics import ConfigureStudyRequest

        req = ConfigureStudyRequest(
            course_id=uuid.uuid4(),
            study_name="Spring 2026 Ablation",
            groups={
                "control": {"features_disabled": ["memory", "strategy"]},
                "treatment": {"features_disabled": []},
            },
            randomization_seed=42,
        )
        assert len(req.groups) == 2


class TestCourseSchemas:
    """Verify course endpoint response models."""

    def test_course_detail_response(self):
        from docere.api.courses import CourseDetailResponse

        resp = CourseDetailResponse(
            id=str(uuid.uuid4()),
            name="CS101",
            course_code="CS101",
            student_count=35,
            material_count=12,
            assignment_count=8,
        )
        assert resp.student_count == 35

    def test_upload_material_response(self):
        from docere.api.courses import UploadMaterialResponse

        resp = UploadMaterialResponse(
            id=str(uuid.uuid4()),
            title="Extra Notes",
            material_type="supplement",
            status="created",
        )
        assert resp.status == "created"


class TestLMSSchemas:
    """Verify LMS webhook response models."""

    def test_webhook_response(self):
        from docere.api.lms import WebhookResponse

        resp = WebhookResponse(status="received", events_processed=3)
        assert resp.events_processed == 3

    def test_webhook_response_defaults(self):
        from docere.api.lms import WebhookResponse

        resp = WebhookResponse(status="received")
        assert resp.events_processed == 0
