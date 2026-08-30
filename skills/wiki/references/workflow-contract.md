# Workflow Contract

Read this reference when initializing a governed Wiki, submitting a page, or
recovering from a non-zero CLI exit.

## Governed initialization

Run `wiki classify`, then `wiki init --locale en|zh-CN|ja`. The classifier and
built-in template registry own the complete structure and its localized labels.
Callers may select only an exact locale and, when necessary, a registered
primary template override. They cannot supply structure nodes,
`direct_source_paths`, or `documentation_only`.

## Page input

```json
{
  "schema_version": "2.0",
  "page_id": "architecture",
  "subsections": [
    {
      "subsection_id": "runtime_flow",
      "body": "Markdown below the CLI-owned H4; only H5/H6 are allowed.\n",
      "evidence_ids": ["evidence:..."]
    }
  ]
}
```

The Subsection array must exactly match persisted contract order. Every
implementation Subsection cites at least one returned `role: direct` item whose
coverage includes that Subsection. Submit from a temporary file or stdin:

```bash
repo-dive wiki page <repository> \
  --page architecture \
  --input page.json \
  --format json
```

## Command sequence

```bash
repo-dive index <repository> --format json
repo-dive wiki classify <repository> --format json
repo-dive wiki init <repository> --locale en --format json
repo-dive wiki evidence <repository> --page <page-id> \
  --token-budget 8000 --max-results 40 --format json
repo-dive wiki page <repository> --page <page-id> \
  --input page.json --format json
repo-dive wiki status <repository> --format json
repo-dive wiki validate <repository> --format json
repo-dive wiki build <repository> --format json
```

## Exit and recovery rules

| Exit | Meaning | Action |
| --- | --- | --- |
| `0` | Success | Parse the single stdout document. |
| `2` | Invalid invocation or input | Correct arguments or JSON; never retry unchanged. |
| `3` | Repository, index, or Wiki state condition | Recover using the stable error code. |
| `4` | Internal operation failure | Surface the safe diagnostic and preserve the last valid artifact. |

Common exit-3 recovery:

- `index_not_found` or `index_stale`: rerun `index` with the same Corpus
  parameters, then retry the interrupted stage.
- `wiki_not_initialized`: submit `wiki init`.
- `wiki_evidence_direct_budget_insufficient`: increase the explicit budget;
  no Page state was mutated.
- `wiki_evidence_stale`: recollect Evidence and regenerate only the listed
  pages.
- `wiki_build_incomplete`: inspect `wiki status`, then finish the listed pages.
- `wiki_evidence_empty`: increase the positive budget or improve the page query
  and Corpus; do not invent citations.

stdout is the machine contract. stderr is diagnostic text and must never be
parsed as source Evidence.

## Artifact contract

```text
<repository>/.repo-dive/
├── wiki.md
├── wiki.json
├── metadata.json
├── index
└── index-generations/
```

Consume `wiki.md` only after a successful Build. Do not modify the analyzed
repository's `.gitignore` automatically.
