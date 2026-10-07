"""Sampling parameters shared by every task."""

from pydantic import BaseModel, Field


class GenParams(BaseModel):
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, gt=0, le=1)
    max_tokens: int | None = Field(default=None, ge=16, le=8192)

    def ollama_options(self, default_temp: float, default_max: int, num_ctx: int) -> dict:
        return {
            "temperature": self.temperature if self.temperature is not None else default_temp,
            "top_p": self.top_p if self.top_p is not None else 0.9,
            "num_predict": self.max_tokens or default_max,
            "num_ctx": num_ctx,
        }
