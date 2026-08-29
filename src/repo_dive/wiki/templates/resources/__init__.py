"""Bundled Markdown generation guidance for Wiki template contributions."""

from importlib.resources import files


def read_guidance_resource(resource_name: str) -> str:
    """Read one registered POSIX resource path as UTF-8 text."""
    parts = resource_name.split("/")
    if (
        len(parts) != 3
        or any(part in {"", ".", ".."} for part in parts)
        or "\\" in resource_name
        or not parts[-1].endswith(".md")
    ):
        raise ValueError("guidance resource name must be a safe registered path")
    return files(__name__).joinpath(*parts).read_text(encoding="utf-8")


__all__ = ["read_guidance_resource"]
