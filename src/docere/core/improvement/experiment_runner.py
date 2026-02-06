"""Experiment runner: manages A/B testing of strategy selection."""


class ExperimentRunner:
    """Manages strategy experiments and tracks results."""

    async def get_active_experiment(self, course_id: str) -> dict[str, object] | None:
        """Get the active experiment configuration for a course."""
        # TODO: Fetch from study_config
        raise NotImplementedError
