---
name: wiki
description: Generate or refresh an evidence-grounded repository Wiki with the repo-dive CLI. Use when asked to document a codebase, explain its architecture, create onboarding documentation, or build a repository Wiki.
---

# Repo Dive Wiki Generation

Use the installed `repo-dive` executable as the deterministic evidence and
artifact engine. Use the current Agent model only for structure design and page
prose. Never imply that the CLI calls a generative model.

## Interpret the request

- Repository defaults to the current workspace root.
- Language defaults to the user's language.
- Scope defaults to a professional architecture and developer Wiki sized to
  the repository. Do not force a fixed number of pages.
- A URL is not a local repository path; do not clone it unless the user has
  separately authorized cloning.

## Preflight

1. Resolve the local repository root and inspect its instructions and primary
   documentation.
2. Run `command -v repo-dive`, `repo-dive --version`, and
   `repo-dive wiki --help`. Prefer a compatible executable already on `PATH`.
   If it is unavailable, do not silently download or install software. Explain
   that Repo Dive 0.1.0 will be downloaded from the `sjin66/repo-dive` GitHub
   Release, SHA-256 verified, and installed outside the Skill in the user cache.
   State the cache destination and ask for explicit consent before continuing.
3. Only after consent, run `scripts/repo-dive --install` on macOS or
   `scripts/repo-dive.ps1 --install` with PowerShell on Windows. Unsupported
   platforms stop before network access. A checksum or archive-safety failure
   stops the workflow; never bypass verification. The normal launcher path
   never downloads. After installation, invoke the same launcher without
   `--install` for every CLI stage. It forwards arguments, standard streams,
   and the CLI exit code unchanged.
4. Inspect `git status --short` and preserve all existing user changes.
5. Choose explicit `--exclude` patterns for high-noise agent configuration,
   generated output, vendored dependencies, fixtures, and plans when they are
   not documentation targets. Keep tests when the Wiki must explain behavior
   or verification.

## Required workflow

Every functional `repo-dive` command below uses `--format json`. Treat stdout as
exactly one JSON document, diagnostics as stderr-only text, and require exit
code `0` before advancing.

1. Run `repo-dive index <repository> ... --format json`. Save the exact
   Include/Exclude parameters because later freshness checks reuse them.
2. Design stable Wiki sections and page IDs. Each page needs a focused
   description, real `relevant_files`, and useful `related_page_ids`.
3. Put `structure.json` in a temporary directory outside the analyzed
   repository. Writing orchestration inputs inside the repository after
   indexing makes the index stale.
4. Submit it with `repo-dive wiki structure <repository> --input structure.json
   --format json`.
5. For every page, run `repo-dive wiki evidence <repository> --page <page-id>
   --token-budget <tokens> --format json` and review the returned Evidence
   before writing. Use 4,000–8,000 tokens for substantial pages and a bounded
   result count appropriate to the repository.
6. Generate one Markdown body with the current Agent model using only that
   page's Evidence. Explain design intent and trade-offs, not just syntax. Add
   diagrams only when supported by Evidence. Do not repeat the page title.
7. Submit the body with exact selected `evidence_id` values using
   `repo-dive wiki page <repository> --page <page-id> --input page.json
   --format json`. Citations must belong to the current page snapshot.
8. Repeat Evidence collection and page submission sequentially. These commands
   update one shared `wiki.json`; do not run their writes concurrently.
9. Run `repo-dive wiki status <repository> --format json` until every page is
   `generated` and `complete` is true.
10. Run `repo-dive wiki build <repository> --format json`, require exit code
    `0`, and report the final `<repository>/.repo-dive/wiki.md` path.

Read [the workflow contract](references/workflow-contract.md) before creating
JSON inputs or recovering from a failed command.
Release target and cache details are pinned in
[`references/release.json`](references/release.json); do not construct a
different download URL or modify an installed Skill directory.

## Evidence quality

- If Evidence is dominated by tests, plans, duplicated translations, or agent
  configuration, improve index exclusions or narrow the page description and
  relevant files. Reindex and resubmit the same structure; regenerate only
  pages the CLI marks invalid.
- Prefer exact symbol and function names in page descriptions for structural
  retrieval.
- Do not replace `wiki evidence` with generic `context`. Generic Context is for
  ad hoc answers and does not persist the snapshot required by `wiki page` and
  `wiki build`.
- Never cite Evidence that was not returned for the current page.
- Treat `truncated: true` as a budget signal, not partial source text: the
  packer includes complete Chunks only.

## Completion checks

- `wiki status` reports no pending, failed, or evidence-ready pages.
- `wiki build` reports the expected page, section, and source counts.
- The final Markdown contains a contents section, page headings, source links,
  and every requested diagram or topic.
- Run an unchanged second Build when practical; it should return
  `changed: false` with the same SHA-256.
- Confirm `git status --short` contains no unexpected tracked-file changes.
- Report excluded Corpus areas and any evidence-quality limitations.
