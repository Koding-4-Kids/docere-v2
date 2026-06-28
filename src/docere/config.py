"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://docere:docere_dev@localhost:5432/docere"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"

    # LLM Provider
    llm_provider: str = "anthropic"  # "openai" or "anthropic"

    # Anthropic
    anthropic_api_key: str = ""
    default_model: str = "claude-sonnet-4-20250514"

    # OpenAI
    openai_default_model: str = "gpt-4o-mini"

    # Embeddings
    voyage_api_key: str = ""
    openai_api_key: str = ""
    embedding_model: str = "voyage-3"
    embedding_dimensions: int = 1536  # 1536 for OpenAI text-embedding-3-small, 1024 for Voyage

    # JWT
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440

    # LTI 1.3
    lti_issuer: str = ""
    lti_client_id: str = ""
    lti_deployment_id: str = ""
    lti_jwks_url: str = ""

    # URLs (for LTI redirect_uri and post-launch redirect)
    app_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"

    # Canvas
    canvas_base_url: str = ""
    canvas_api_token: str = ""

    # Moodle
    moodle_base_url: str = ""
    moodle_api_token: str = ""

    # Environment
    environment: str = "development"
    debug: bool = True

    # Memory layer thresholds
    memory_similarity_threshold: float = 0.60
    memory_diversity_threshold: float = 0.65
    memory_max_context_tokens: int = 4000
    memory_compression_threshold: int = 50

    # Process verification
    verification_helpfulness_weight: float = 0.35
    verification_clarity_weight: float = 0.25
    verification_understanding_weight: float = 0.25
    verification_engagement_weight: float = 0.15
    verification_followup_timeout_seconds: int = 300

    # Self-improvement
    strategy_min_uses_for_prune: int = 20
    strategy_prune_score_threshold: float = 0.3
    strategy_evolution_top_k: int = 3

    # Google Calendar integration
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/calendar/oauth/callback"
    # Fernet key. Generate with:
    # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    token_encryption_key: str = ""

    # Student document ingestion
    student_doc_max_file_size_mb: int = 500
    student_doc_max_pages: int = 2000
    student_doc_upload_dir: str = "/tmp/docere_uploads"
    student_doc_storage_dir: str = "data/student_docs"  # Persistent file storage
    student_doc_collection_prefix: str = "student_docs"
    student_doc_max_per_course: int = 20

    # Meeting scheduling
    meeting_default_duration_minutes: int = 30
    meeting_struggle_threshold: float = 0.6
    meeting_struggle_consecutive_count: int = 3

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
