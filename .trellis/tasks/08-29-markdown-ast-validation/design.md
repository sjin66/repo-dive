# Design

Use `markdown-it-py>=4.2,<4.3` with an explicitly constructed CommonMark parser, HTML
tokenization for rejection, and only the table rule enabled. Normalize tokens into a
narrow internal tree so the template validator is parser-adapter independent. Inline
violations inherit the enclosing block's line map. Diagnostics contain stable IDs,
locations, and bounded expected/actual metadata only. Persisted governance records the
exact parser package/version; a version change cannot silently reuse the same profile
identity. The engine consumes the shell contract from the template child rather than
inventing assembler output. Rollback removes the parser adapter before Schema `2.0`
depends on it.
