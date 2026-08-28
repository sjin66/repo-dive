import pytest

from repo_dive.errors import (
    ExitCode,
    InternalOperationError,
    InvocationError,
    RepoDiveError,
    RepositoryError,
)


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
