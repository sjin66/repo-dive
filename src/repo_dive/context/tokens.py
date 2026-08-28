"""Replaceable, deterministic token-estimation contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class TokenEstimator(Protocol):
    """Estimate token usage without depending on a specific model runtime."""

    @property
    def name(self) -> str:
        """Return the stable estimator identity reported to callers."""
        ...

    def estimate(self, text: str) -> int:
        """Return a deterministic non-negative token estimate."""
        ...


@dataclass(frozen=True, slots=True)
class ConservativeTokenEstimator:
    """Estimate from UTF-8 bytes using a conservative code-friendly ratio."""

    bytes_per_token: int = 3
    name: str = field(default="conservative_utf8_bytes_v1", init=False)

    def __post_init__(self) -> None:
        if self.bytes_per_token <= 0:
            raise ValueError("bytes_per_token must be positive")

    def estimate(self, text: str) -> int:
        byte_count = len(text.encode("utf-8", errors="surrogatepass"))
        return (byte_count + self.bytes_per_token - 1) // self.bytes_per_token


__all__ = ["ConservativeTokenEstimator", "TokenEstimator"]
