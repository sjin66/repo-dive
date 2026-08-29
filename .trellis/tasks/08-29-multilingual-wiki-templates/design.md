# Design

Bundle language-neutral contract contributions, localized Markdown guidance, and exact
locale catalogs under one registry. Compose by logical ID using the closed operations
in the parent design. Compute separate canonical hashes for validation rules and
localized guidance. Validate complete locale key parity and resource registration at
load/test time; no fallback or dynamic plugin/template loading is allowed.

The framework shell is defined here, including localized root/contents/section/page,
related-page, and source nodes, so the later validator has a complete final-document
contract before assembler integration. Template contracts use their independent Schema
`1.0`; a future Wiki state Schema `2.0` snapshot may embed that identity without changing
the template schema. Rollback removes only unreferenced bundled resources before state
integration; registry conflicts fail package tests rather than runtime fallback.
