"""Explicit local-only embedding provider boundary."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Sequence
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

from repo_dive.errors import InternalOperationError, InvocationError
from repo_dive.indexing.vectors import (
    EmbeddingIdentity,
    pack_float32,
    unpack_float32,
)

DEFAULT_EMBEDDING_BATCH_SIZE = 32


class EmbeddingProvider(Protocol):
    """A typed batch embedding source with an explicit vector-space identity."""

    @property
    def identity(self) -> EmbeddingIdentity:
        """Return the provider, model, and output dimensions."""
        ...

    def embed(
        self,
        texts: Sequence[str],
        *,
        batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
    ) -> tuple[tuple[float, ...], ...]:
        """Embed one ordered text batch at stable float32 precision."""
        ...


class _SentenceTransformerModel(Protocol):
    def get_embedding_dimension(self) -> int | None: ...

    def encode(self, inputs: Sequence[str], **kwargs: object) -> object: ...


class SentenceTransformersEmbeddingProvider:
    """Lazy Sentence Transformers adapter restricted to one local model directory."""

    def __init__(self, model_path: str | Path) -> None:
        resolved = _resolve_local_model(model_path)
        module = _import_sentence_transformers()
        self._model = _load_model(module, resolved)
        try:
            dimensions = self._model.get_embedding_dimension()
        except Exception as error:
            raise _model_load_error() from error
        if type(dimensions) is not int or dimensions <= 0:
            raise _model_load_error()
        self._identity = EmbeddingIdentity(
            provider="sentence-transformers",
            model=_local_model_identity(resolved),
            dimensions=dimensions,
        )

    @property
    def identity(self) -> EmbeddingIdentity:
        """Return an opaque local model identity and its output dimensions."""
        return self._identity

    def embed(
        self,
        texts: Sequence[str],
        *,
        batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
    ) -> tuple[tuple[float, ...], ...]:
        """Embed one ordered batch without progress output or network fallback."""
        ordered = _validate_texts(texts)
        if type(batch_size) is not int or batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if not ordered:
            return ()
        try:
            raw = self._model.encode(
                ordered,
                batch_size=batch_size,
                convert_to_numpy=True,
                convert_to_tensor=False,
                normalize_embeddings=False,
                precision="float32",
                show_progress_bar=False,
            )
        except Exception as error:
            raise InternalOperationError(
                "embedding_failed",
                "Could not compute local embeddings.",
            ) from error
        try:
            return _validated_embeddings(
                raw,
                expected_count=len(ordered),
                dimensions=self.identity.dimensions,
            )
        except (TypeError, ValueError, OverflowError) as error:
            raise InternalOperationError(
                "embedding_output_invalid",
                "Embedding provider returned invalid vectors.",
            ) from error


def _resolve_local_model(model_path: str | Path) -> Path:
    try:
        resolved = Path(model_path).resolve(strict=True)
    except (OSError, RuntimeError, ValueError, TypeError) as error:
        raise InvocationError(
            "embedding_model_invalid",
            "Embedding model must be an existing local directory.",
        ) from error
    if not resolved.is_dir():
        raise InvocationError(
            "embedding_model_invalid",
            "Embedding model must be an existing local directory.",
        )
    return resolved


def _local_model_identity(model_path: Path) -> str:
    encoded = str(model_path).encode("utf-8", errors="surrogateescape")
    return f"local:{hashlib.sha256(encoded).hexdigest()}"


def _import_sentence_transformers() -> ModuleType:
    try:
        return import_module("sentence_transformers")
    except (ImportError, ModuleNotFoundError) as error:
        raise InvocationError(
            "embedding_provider_unavailable",
            "Sentence Transformers support is unavailable; install repo-dive[vector].",
        ) from error


def _load_model(module: ModuleType, model_path: Path) -> _SentenceTransformerModel:
    factory = cast(
        Callable[..., object] | None,
        getattr(module, "SentenceTransformer", None),
    )
    if factory is None or not callable(factory):
        raise InvocationError(
            "embedding_provider_unavailable",
            "Sentence Transformers support is unavailable; install repo-dive[vector].",
        )
    try:
        model = factory(
            str(model_path),
            local_files_only=True,
            trust_remote_code=False,
        )
    except Exception as error:
        raise _model_load_error() from error
    return cast(_SentenceTransformerModel, model)


def _model_load_error() -> InternalOperationError:
    return InternalOperationError(
        "embedding_model_load_failed",
        "Could not load the local embedding model.",
    )


def _validate_texts(texts: Sequence[str]) -> tuple[str, ...]:
    if (
        isinstance(texts, (str, bytes))
        or not isinstance(texts, Sequence)
        or any(not isinstance(text, str) for text in texts)
    ):
        raise ValueError("texts must be a sequence of strings")
    return tuple(texts)


def _validated_embeddings(
    value: object,
    *,
    expected_count: int,
    dimensions: int,
) -> tuple[tuple[float, ...], ...]:
    rows = _as_items(value)
    if len(rows) != expected_count:
        raise ValueError("embedding count does not match input count")
    embeddings: list[tuple[float, ...]] = []
    for row in rows:
        row_value = _to_list(row)
        values = cast(Iterable[float], _as_items(row_value))
        encoded = pack_float32(values, dimensions=dimensions)
        embeddings.append(unpack_float32(encoded, dimensions=dimensions))
    return tuple(embeddings)


def _to_list(value: object) -> object:
    method = cast(Callable[[], object] | None, getattr(value, "tolist", None))
    return method() if callable(method) else value


def _as_items(value: object) -> tuple[object, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        raise TypeError("embedding output must be an iterable matrix")
    return tuple(value)


__all__ = [
    "DEFAULT_EMBEDDING_BATCH_SIZE",
    "EmbeddingProvider",
    "SentenceTransformersEmbeddingProvider",
]
