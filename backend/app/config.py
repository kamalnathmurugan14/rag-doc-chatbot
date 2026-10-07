"""Application settings: one class, read from backend/.env (see .env.example)."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "0.1.0"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    docs_root: Path = Path("./sample_docs")
    data_dir: Path = Path("./data")
    max_upload_mb: int = 25
    allowed_extensions: str = "pdf,docx,txt,md"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    chunk_tokens: int = 600
    chunk_overlap_pct: int = 12
    top_k: int = 5
    fetch_k: int = 20
    use_mmr: bool = True
    mmr_lambda: float = 0.6
    use_reranker: bool = False
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    min_similarity: float = 0.25
    max_history_turns: int = 6
    temperature: float = 0.1
    context_tokens: int = 4096
    max_answer_tokens: int = 700
    llm_timeout_s: float = 300.0
    cors_origins: str = "http://localhost:5173"

    @field_validator("mmr_lambda", "min_similarity")
    @classmethod
    def _unit(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("must be between 0 and 1")
        return v

    @field_validator("chunk_overlap_pct")
    @classmethod
    def _pct(cls, v: int) -> int:
        if not 0 <= v <= 50:
            raise ValueError("CHUNK_OVERLAP_PCT must be 0-50")
        return v

    @property
    def extensions(self) -> set[str]:
        return {e.strip().lower().lstrip(".") for e in self.allowed_extensions.split(",") if e.strip()}

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def db_path(self) -> Path:
        return self.data_dir / "chat.sqlite"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    # LLMClient (copied from project 3) reads these names
    @property
    def default_temperature(self) -> float:
        return self.temperature

    @property
    def default_max_tokens(self) -> int:
        return self.max_answer_tokens


@lru_cache
def get_settings() -> Settings:
    return Settings()
