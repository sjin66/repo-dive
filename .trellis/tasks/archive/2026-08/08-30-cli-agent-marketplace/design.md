# Design: Self-contained marketplace CLI

## Architecture

The implementation keeps three boundaries explicit:

1. `repo-dive` remains the deterministic Python CLI and owns no Agent or model
   runtime behavior.
2. `skills/wiki/` remains the only operational Skill source and gains thin,
   cross-platform bootstrap launchers plus release metadata.
3. GitHub Releases for `sjin66/repo-dive` own platform runtime archives, checksums,
   and provenance attestations.

The Skill will continue to work with an already installed compatible
`repo-dive` command. When one is unavailable, it asks the user for download
consent and invokes its platform bootstrap explicitly. No download occurs merely
because OpenCode loads the Skill.

## Release Artifacts

Use PyInstaller console-mode `onedir` bundles built natively for each target and
publish the complete directories as platform archives:

```text
repo-dive-v<version>-darwin-arm64.tar.gz
repo-dive-v<version>-darwin-x64.tar.gz
repo-dive-v<version>-windows-x64.zip
SHA256SUMS
```

Each archive has exactly one top-level directory and a stable executable path:

```text
repo-dive/
├── repo-dive              # repo-dive.exe on Windows
└── _internal/             # Python runtime, application, native libraries, data
```

This follows the `colbymchenry/codegraph` distribution boundary: Agent-facing
integration remains small while a versioned platform archive owns the language
runtime, application, and parser implementation. PyInstaller is retained only
as Repo Dive's directory assembler so the project does not add and qualify a
second portable-CPython distribution source. The result is an inspectable,
natively tested runtime directory rather than a self-extracting executable.

The checked-in spec/build configuration must explicitly collect the dynamically
imported `tree_sitter`, `tree_sitter_javascript`, and `tree_sitter_typescript`
modules and the existing `repo_dive/_skills/wiki` package resources. Optional
vector dependencies are absent from the build environment. Archive creation
must be deterministic enough for release checks to assert layout and content
closure; reproducible byte-for-byte archives are not an MVP requirement.

Each target is built on its native GitHub Actions runner. A tag-triggered release
workflow runs repository checks, builds all matrix entries, archives each
directory, extracts it into a clean location, executes native smoke tests,
computes `SHA256SUMS`, publishes one release only after every target passes, and
emits GitHub artifact attestations. Release assets and the Skill use the same
package version and `v<version>` tag.

OS vendor signing is deferred. The release notes and bilingual documentation
state this limitation; signing can be inserted between build and publish later
without changing the launcher contract.

## Skill Package

The authoritative Skill gains resources similar to:

```text
skills/wiki/
├── SKILL.md
├── references/
│   ├── workflow-contract.md
│   └── release.json
└── scripts/
    ├── repo-dive
    └── repo-dive.ps1
```

`release.json` is a stable machine contract containing schema version, package
version, public repository, release tag, and target-to-archive mapping including
archive type, top-level directory, and executable-relative path. Contract tests
require its version to match `pyproject.toml`, `repo_dive.__version__`, and all
plugin manifests. The launchers contain behavior only; they read this metadata
rather than duplicating release URLs or bundle layout.

OpenCode continues to consume the shared Agent Skill. Project installation uses
`.agents/skills/wiki`; global `npx skills` installation uses OpenCode's global
Skill directory. No `.opencode/plugins/repo-dive.*` runtime is introduced.
The application modules remain in the checksummed platform archive rather than
the Skill, keeping application code, interpreter, and Tree-sitter ABI at one
atomic release version while the Skill stays small.

## Bootstrap Contract

The POSIX launcher supports macOS and the PowerShell launcher supports Windows.
Both expose equivalent behavior:

1. Read and validate bundled release metadata.
2. Normalize the host to `darwin-arm64`, `darwin-x64`, or `windows-x64`.
3. Reject unknown and unsupported targets before any network operation.
4. Resolve a versioned per-user cache path outside the installed Skill:
   `${XDG_CACHE_HOME:-$HOME/.cache}/repo-dive/<version>/<target>/` on macOS and
   `%LOCALAPPDATA%\repo-dive\<version>\<target>\` on Windows.
5. For normal execution, require a completed-install marker and the executable at
   the metadata-declared relative path, then replace the launcher process while
   forwarding all arguments and standard streams. Return the child exit status
   unchanged.
6. If the cache is absent, return an actionable diagnostic. Never download from
   the normal execution path.
7. Only an explicit bootstrap install operation, called after Agent-recorded user
   consent, downloads the version-pinned archive and `SHA256SUMS` over HTTPS.
8. Parse the exact archive digest and reject missing, duplicate, or malformed
   entries before extraction.
9. Verify the archive bytes, inspect the member list before writing, and reject
   absolute paths, parent traversal, unexpected top-level entries, and links that
   could escape the extraction root.
10. Extract into a temporary sibling directory, validate the declared layout,
    set executable permissions where applicable, smoke `--version`, write the
    completed-install marker, and atomically rename the whole directory into the
    cache.
11. Preserve the previous valid cache on download, checksum, extraction, smoke,
    or publication failure. Concurrent installers either reuse the completed
    cache or publish the same verified directory safely.

The Skill preflight prefers an already available compatible CLI, preserving the
existing source/wheel workflow. Otherwise it explains the exact source, version,
cache destination, and network action; asks for consent; performs the explicit
bootstrap; and uses the bundled launcher for every subsequent CLI stage.

## Upgrade And Removal

`npx skills update wiki` updates the Skill and its pinned release metadata. A new
version resolves to a new cache directory, so a failed upgrade cannot corrupt a
working older version. Old versions are not silently deleted.

`npx skills remove wiki` removes only the Skill. Documentation gives explicit,
platform-specific commands to remove Repo Dive's cache after inspecting it.
Neither path touches a repository's `.repo-dive/` directory.

## Validation

Default tests stay offline and deterministic:

- validate release metadata schema, version consistency, HTTPS URLs, target
  closure, and Skill resource closure;
- exercise platform normalization, no-network unsupported behavior, consent
  boundary, checksum rejection, malicious archive rejection, atomic directory
  publication, cache reuse, argument forwarding, and exit-code propagation with
  controlled command fixtures;
- preserve existing Agent Plugin, `init`, wheel/sdist, JSON, and CLI tests.

Native release smoke tests extract the published archive into a clean directory,
execute the bundled launcher, and index small JavaScript and TypeScript fixtures.
They assert successful JSON output and the absence of
`tree_sitter_unavailable`, proving native grammar libraries were collected rather
than silently falling back to text parsing.

Post-build validation checks artifact names and SHA-256 entries. Vendor smoke
tests may install the tagged public Skill with `npx skills` and verify OpenCode's
discovery path without requiring a model call in the default test suite.

## Rollback

- A failed build publishes no GitHub Release.
- A failed bootstrap leaves the previous cache untouched and removes temporary
  files where possible.
- A faulty release is withdrawn or superseded; updating the Skill pins the fixed
  version without mutating repository artifacts.
- Existing pip/source installation remains an independent fallback.
