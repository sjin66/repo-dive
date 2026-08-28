"""Private persistent repository index."""

from repo_dive.indexing.service import (
    IndexBuildResult,
    IndexService,
    PublishedIndex,
    load_published_index,
)
from repo_dive.indexing.store import INDEX_SCHEMA_VERSION, IndexStore
from repo_dive.indexing.vectors import (
    ChunkVector,
    EmbeddingIdentity,
    create_chunk_vector,
)

__all__ = [
    "INDEX_SCHEMA_VERSION",
    "ChunkVector",
    "EmbeddingIdentity",
    "IndexBuildResult",
    "IndexService",
    "IndexStore",
    "PublishedIndex",
    "create_chunk_vector",
    "load_published_index",
]
