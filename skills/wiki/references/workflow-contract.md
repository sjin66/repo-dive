# Workflow Contract

Read this reference when preparing `structure.json`, submitting a page, or
recovering from a non-zero CLI exit.

## Structure input

Keep this file outside the analyzed repository after indexing.

```json
{
  "schema_version": "1.0",
  "title": "Project Wiki",
  "description": "Audience and scope.",
  "output_language": "en",
  "sections": [
    {
      "id": "foundations",
      "title": "Foundations",
      "pages": [
        {
          "id": "architecture",
          "title": "System Architecture",
          "description": "Explain exact modules, entry points, and data flow.",
          "relevant_files": ["src/project/cli.py"],
          "related_page_ids": []
        }
      ]
    }
  ]
}
```

Use unique, stable IDs. Every relevant path must exist inside the indexed
repository. Do not supply lifecycle fields such as status, body, Evidence, or
errors; the CLI owns them.

## Page input

```json
{
  "schema_version": "1.0",
  "page_id": "architecture",
  "body": "Markdown body without a repeated page title.\n",
  "evidence_ids": ["evidence:..."]
}
```

The array must be non-empty and contain unique IDs from the current page's
persisted Evidence snapshot. Submit from a temporary file or stdin:

```bash
repo-dive wiki page <repository> \
  --page architecture \
  --input page.json \
  --format json
```

## Command sequence

```bash
repo-dive index <repository> --format json
repo-dive wiki structure <repository> --input structure.json --format json
repo-dive wiki evidence <repository> --page <page-id> \
  --token-budget 8000 --max-results 40 --format json
repo-dive wiki page <repository> --page <page-id> \
  --input page.json --format json
repo-dive wiki status <repository> --format json
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
- `wiki_not_initialized`: submit `wiki structure`.
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
