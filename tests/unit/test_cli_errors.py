import pytest

from repo_dive.cli import _map_error_details
from repo_dive.errors import (
    ExitCode,
    InternalOperationError,
    InvocationError,
    RepoDiveError,
    RepositoryError,
)
from repo_dive.schema import JsonObject


@pytest.mark.parametrize(
    ("error", "exit_code"),
    [
        (InvocationError("invalid_argument", "Invalid argument."), ExitCode.INVOCATION),
        (
            RepositoryError("repository_not_found", "Repository not found."),
            ExitCode.REPOSITORY,
        ),
        (
            InternalOperationError("index_failed", "Index build failed."),
            ExitCode.INTERNAL,
        ),
    ],
)
def test_domain_errors_have_stable_exit_codes(
    error: RepoDiveError, exit_code: ExitCode
) -> None:
    assert error.exit_code == exit_code


def test_domain_error_preserves_machine_code_and_safe_details() -> None:
    error = RepositoryError(
        "repository_not_found",
        "Repository not found.",
        details={"path": "missing"},
    )

    assert error.code == "repository_not_found"
    assert error.message == "Repository not found."
    assert error.details == {"path": "missing"}


def test_map_missing_index_error_removes_only_the_unsafe_path() -> None:
    error = RepositoryError(
        "index_not_found",
        "Repository index does not exist.",
        details={"path": "/private/repository/.repo-dive/index"},
    )

    adapted = _map_error_details("map validate", error)

    assert adapted.code == error.code
    assert adapted.message == error.message
    assert adapted.exit_code == error.exit_code
    assert adapted.details == {
        "recovery_action": "index_repository",
        "retry_mode": "after_recovery",
    }


def test_non_map_missing_index_error_preserves_existing_details() -> None:
    details: JsonObject = {"path": "/private/repository/.repo-dive/index"}
    error = RepositoryError(
        "index_not_found",
        "Repository index does not exist.",
        details=details,
    )

    adapted = _map_error_details("search", error)

    assert adapted is error
    assert adapted.details == details
