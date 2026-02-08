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
    llm_provider: str = "openai"  # "openai" or "anthropic"

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
    jwt_secret: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440

    # LTI 1.3
    lti_issuer: str = ""
    lti_client_id: str = ""
    lti_deployment_id: str = ""
    lti_jwks_url: str = ""

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
