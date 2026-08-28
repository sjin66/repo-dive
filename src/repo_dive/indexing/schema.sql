BEGIN IMMEDIATE;

CREATE TABLE files (
    path TEXT PRIMARY KEY,
    language TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    content_hash TEXT,
    encoding TEXT,
    status TEXT NOT NULL CHECK (status IN ('read', 'skipped')),
    skip_reason TEXT
);

CREATE TABLE symbols (
    id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    qualified_name TEXT NOT NULL,
    qualified_name_normalized TEXT NOT NULL,
    start_line INTEGER NOT NULL CHECK (start_line >= 1),
    end_line INTEGER NOT NULL CHECK (end_line >= start_line),
    UNIQUE (file_path, ordinal),
    UNIQUE (file_path, kind, qualified_name, start_line, end_line)
);

CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    start_line INTEGER NOT NULL CHECK (start_line >= 1),
    end_line INTEGER NOT NULL CHECK (end_line >= start_line),
    text TEXT NOT NULL,
    symbol_id TEXT REFERENCES symbols(id) ON DELETE SET NULL,
    content_hash TEXT NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0 CHECK (token_count >= 0),
    UNIQUE (file_path, ordinal)
);

CREATE TABLE relationships (
    file_path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    source_id TEXT NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    target_id TEXT NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    source TEXT NOT NULL,
    PRIMARY KEY (source_id, target_id, kind, source),
    UNIQUE (file_path, ordinal)
);

CREATE TABLE terms (
    id INTEGER PRIMARY KEY,
    term TEXT NOT NULL UNIQUE,
    document_frequency INTEGER NOT NULL CHECK (document_frequency > 0)
);

CREATE TABLE postings (
    term_id INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    chunk_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    term_frequency INTEGER NOT NULL CHECK (term_frequency > 0),
    PRIMARY KEY (term_id, chunk_id)
);

CREATE TABLE stats (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE vectors (
    chunk_id TEXT PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    dimensions INTEGER NOT NULL CHECK (dimensions > 0),
    chunk_hash TEXT NOT NULL,
    embedding BLOB NOT NULL,
    CHECK (length(embedding) = dimensions * 4)
);

CREATE INDEX symbols_name_lookup
ON symbols (name, qualified_name, file_path);

CREATE INDEX symbols_normalized_name_lookup
ON symbols (name_normalized, qualified_name_normalized, file_path);

CREATE INDEX relationships_source_lookup
ON relationships (source_id, kind, target_id);

CREATE INDEX relationships_target_lookup
ON relationships (target_id, kind, source_id);

PRAGMA user_version = 4;
COMMIT;
