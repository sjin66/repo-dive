from __future__ import annotations

import hashlib
import math
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

import pytest

from repo_dive.errors import InternalOperationError, InvocationError
from repo_dive.indexing.vectors import EmbeddingIdentity
from repo_dive.providers.embeddings import (
    EmbeddingProvider,
    SentenceTransformersEmbeddingProvider,
)

PROJECT_ROOT = Path(__file__).parents[3]


class FakeProvider:
    def __init__(self) -> None:
        self.identity = EmbeddingIdentity(
            provider="fake",
            model="fixture-v1",
            dimensions=2,
        )
        self.calls: list[tuple[tuple[str, ...], int]] = []

    def embed(
        self,
        texts: Sequence[str],
        *,
        batch_size: int = 32,
    ) -> tuple[tuple[float, ...], ...]:
        self.calls.append((tuple(texts), batch_size))
        return tuple((float(index), 1.0) for index, _ in enumerate(texts))


class FakeSentenceTransformer:
    def __init__(
        self,
        *,
        dimensions: int | None = 3,
        output: object | None = None,
        encode_error: Exception | None = None,
    ) -> None:
        self.dimensions = dimensions
        self.output = output
        self.encode_error = encode_error
        self.encode_calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

    def get_embedding_dimension(self) -> int | None:
        return self.dimensions

    def encode(self, inputs: Sequence[str], **kwargs: object) -> object:
        self.encode_calls.append((tuple(inputs), kwargs))
        if self.encode_error is not None:
            raise self.encode_error
        if self.output is not None:
            return self.output
        return [[float(index), 0.5, -0.25] for index, _ in enumerate(inputs)]


def install_fake_module(
    monkeypatch: pytest.MonkeyPatch,
    model: FakeSentenceTransformer,
    constructor_calls: list[tuple[str, dict[str, object]]],
) -> None:
    module = ModuleType("sentence_transformers")

    def factory(model_path: str, **kwargs: object) -> FakeSentenceTransformer:
        constructor_calls.append((model_path, kwargs))
        return model

    module.__dict__["SentenceTransformer"] = factory
    monkeypatch.setattr(
        "repo_dive.providers.embeddings.import_module",
        lambda name: module,
    )


def test_fake_provider_contract_covers_batching_dimensions_and_identity() -> None:
    provider: EmbeddingProvider = FakeProvider()

    vectors = provider.embed(("alpha", "beta"), batch_size=2)

    assert provider.identity == EmbeddingIdentity(
        provider="fake",
        model="fixture-v1",
        dimensions=2,
    )
    assert vectors == ((0.0, 1.0), (1.0, 1.0))
    assert len(vectors[0]) == provider.identity.dimensions


def test_importing_adapter_does_not_import_sentence_transformers() -> None:
    assert "sentence_transformers" not in sys.modules


def test_sentence_transformers_is_available_only_through_vector_extra() -> None:
    document = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert not any(
        dependency.startswith("sentence-transformers")
        for dependency in document["project"]["dependencies"]
    )
    assert document["project"]["optional-dependencies"]["vector"] == [
        "sentence-transformers>=6.0,<7.0"
    ]


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_provider_requires_an_existing_local_model_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    model_path = tmp_path / "model"
    if kind == "file":
        model_path.write_text("not a directory", encoding="utf-8")

    def reject_import(name: str) -> ModuleType:
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.setattr(
        "repo_dive.providers.embeddings.import_module",
        reject_import,
    )

    with pytest.raises(InvocationError) as exc_info:
        SentenceTransformersEmbeddingProvider(model_path)

    assert exc_info.value.code == "embedding_model_invalid"
    assert exc_info.value.details is None
    assert str(model_path) not in str(exc_info.value)


def test_missing_optional_dependency_has_safe_install_guidance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_path = tmp_path / "model"
    model_path.mkdir()

    def missing_dependency(name: str) -> ModuleType:
        raise ModuleNotFoundError(
            "secret dependency traceback",
            name="sentence_transformers",
        )

    monkeypatch.setattr(
        "repo_dive.providers.embeddings.import_module",
        missing_dependency,
    )

    with pytest.raises(InvocationError) as exc_info:
        SentenceTransformersEmbeddingProvider(model_path)

    assert exc_info.value.code == "embedding_provider_unavailable"
    assert "repo-dive[vector]" in str(exc_info.value)
    assert "secret" not in str(exc_info.value)


def test_adapter_loads_only_local_files_and_reports_typed_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_path = tmp_path / "model"
    model_path.mkdir()
    model = FakeSentenceTransformer(dimensions=3)
    constructor_calls: list[tuple[str, dict[str, object]]] = []
    install_fake_module(monkeypatch, model, constructor_calls)

    provider = SentenceTransformersEmbeddingProvider(model_path)

    assert constructor_calls == [
        (
            str(model_path.resolve()),
            {
                "local_files_only": True,
                "trust_remote_code": False,
            },
        )
    ]
    assert provider.identity == EmbeddingIdentity(
        provider="sentence-transformers",
        model=(
            "local:" + hashlib.sha256(str(model_path.resolve()).encode()).hexdigest()
        ),
        dimensions=3,
    )
    assert str(model_path.resolve()) not in provider.identity.model


@pytest.mark.parametrize("dimensions", [None, 0, -1, True])
def test_adapter_rejects_invalid_model_dimensions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    dimensions: int | None,
) -> None:
    model_path = tmp_path / "model"
    model_path.mkdir()
    model = FakeSentenceTransformer(dimensions=dimensions)
    install_fake_module(monkeypatch, model, [])

    with pytest.raises(InternalOperationError) as exc_info:
        SentenceTransformersEmbeddingProvider(model_path)

    assert exc_info.value.code == "embedding_model_load_failed"
    assert exc_info.value.details is None


def test_adapter_embeds_one_batch_with_explicit_float32_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_path = tmp_path / "model"
    model_path.mkdir()
    model = FakeSentenceTransformer(
        output=[[1.0, 0.1, -0.2], [2.0, 0.3, -0.4]],
    )
    install_fake_module(monkeypatch, model, [])
    provider = SentenceTransformersEmbeddingProvider(model_path)

    vectors = provider.embed(("alpha", "beta"), batch_size=2)

    assert vectors == (
        (1.0, 0.10000000149011612, -0.20000000298023224),
        (2.0, 0.30000001192092896, -0.4000000059604645),
    )
    assert model.encode_calls == [
        (
            ("alpha", "beta"),
            {
                "batch_size": 2,
                "convert_to_numpy": True,
                "convert_to_tensor": False,
                "normalize_embeddings": False,
                "precision": "float32",
                "show_progress_bar": False,
            },
        )
    ]


def test_empty_batch_returns_without_calling_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_path = tmp_path / "model"
    model_path.mkdir()
    model = FakeSentenceTransformer()
    install_fake_module(monkeypatch, model, [])
    provider = SentenceTransformersEmbeddingProvider(model_path)

    assert provider.embed(()) == ()
    assert model.encode_calls == []


@pytest.mark.parametrize(
    "output",
    [
        [],
        [[1.0, 2.0]],
        [[1.0, 2.0, math.nan]],
        "not-a-matrix",
    ],
)
def test_adapter_rejects_invalid_provider_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: object,
) -> None:
    model_path = tmp_path / "model"
    model_path.mkdir()
    model = FakeSentenceTransformer(output=output)
    install_fake_module(monkeypatch, model, [])
    provider = SentenceTransformersEmbeddingProvider(model_path)

    with pytest.raises(InternalOperationError) as exc_info:
        provider.embed(("alpha",))

    assert exc_info.value.code == "embedding_output_invalid"
    assert exc_info.value.details is None


@pytest.mark.parametrize("texts", ["alpha", ("alpha", 42)])
def test_adapter_rejects_invalid_batch_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    texts: object,
) -> None:
    model_path = tmp_path / "model"
    model_path.mkdir()
    model = FakeSentenceTransformer()
    install_fake_module(monkeypatch, model, [])
    provider = SentenceTransformersEmbeddingProvider(model_path)

    with pytest.raises(ValueError, match="texts must be a sequence of strings"):
        provider.embed(texts)  # type: ignore[arg-type]


@pytest.mark.parametrize("batch_size", [0, -1, True])
def test_adapter_rejects_invalid_batch_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    batch_size: int,
) -> None:
    model_path = tmp_path / "model"
    model_path.mkdir()
    model = FakeSentenceTransformer()
    install_fake_module(monkeypatch, model, [])
    provider = SentenceTransformersEmbeddingProvider(model_path)

    with pytest.raises(ValueError, match="batch_size must be positive"):
        provider.embed(("alpha",), batch_size=batch_size)


def test_model_load_failure_redacts_provider_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_path = tmp_path / "private-model"
    model_path.mkdir()
    module = ModuleType("sentence_transformers")

    def fail_load(model_path_value: str, **kwargs: object) -> object:
        raise RuntimeError(f"token=super-secret path={model_path_value}")

    module.__dict__["SentenceTransformer"] = fail_load
    monkeypatch.setattr(
        "repo_dive.providers.embeddings.import_module",
        lambda name: module,
    )

    with pytest.raises(InternalOperationError) as exc_info:
        SentenceTransformersEmbeddingProvider(model_path)

    assert exc_info.value.code == "embedding_model_load_failed"
    assert "super-secret" not in str(exc_info.value)
    assert str(model_path) not in str(exc_info.value)
    assert exc_info.value.details is None


def test_embedding_failure_redacts_provider_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_path = tmp_path / "private-model"
    model_path.mkdir()
    model = FakeSentenceTransformer(
        encode_error=RuntimeError("token=super-secret remote stack trace"),
    )
    install_fake_module(monkeypatch, model, [])
    provider = SentenceTransformersEmbeddingProvider(model_path)

    with pytest.raises(InternalOperationError) as exc_info:
        provider.embed(("alpha",))

    assert exc_info.value.code == "embedding_failed"
    assert "super-secret" not in str(exc_info.value)
    assert exc_info.value.details is None
