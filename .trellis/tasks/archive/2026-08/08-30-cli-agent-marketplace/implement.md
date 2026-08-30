# Implementation Plan

## Ordered Checklist

1. Add failing contract tests for release metadata, supported target mapping,
   version consistency, Skill resource closure, and the prohibition on an
   OpenCode runtime plugin.
2. Add failing launcher behavior tests for unsupported targets, absent cache,
   explicit install, checksum mismatch, malicious archive members, atomic
   directory publication, verified cache reuse, argument/stream forwarding, and
   exit-code propagation on POSIX and Windows.
3. Add `skills/wiki/references/release.json`, the POSIX and PowerShell launchers,
   and update `skills/wiki/SKILL.md` to preserve PATH-based use while adding the
   explicit-consent bootstrap workflow.
4. Extend wheel/sdist resource and `repo-dive init` smoke tests so every new Skill
   resource is bundled byte-for-byte from the authoritative source.
5. Add a pinned bundle-build dependency/configuration and a reviewable
   PyInstaller `onedir` spec that collects dynamic Tree-sitter modules, package
   data, and the Python runtime while excluding optional vector/model
   dependencies.
6. Add deterministic-layout tar/zip packaging and a native extracted-bundle
   smoke harness covering archive safety, `--version`, help, JSON output,
   JavaScript indexing, TypeScript indexing, and no Tree-sitter fallback.
7. Add Make targets for local bundle build/smoke without changing the
   required `setup`, `check`, `test-unit`, and `test-all` entry points.
8. Add a tag-gated GitHub Actions release workflow for macOS ARM64, macOS x64,
   and Windows x64. Require checks, archive extraction, and target smoke tests
   before generating `SHA256SUMS`, attestations, and one GitHub Release.
9. Update `.trellis/spec/backend/agent-plugin-contracts.md` for the new
   explicit-consent executable boundary and update matched English/Simplified
   Chinese Agent installation documentation plus README install examples for
   `sjin66/repo-dive` and OpenCode.
10. Run offline validation, inspect the complete diff for source/Skill/release
    version drift, and perform available platform/vendor smoke tests. Record any
    native matrix checks that can run only in GitHub Actions.

## Validation Commands

```bash
make setup
make check
make test-unit
make test-all
make package-smoke
```

Run the new `onedir` archive build/extract/smoke Make target on the current macOS
ARM64 host. The release workflow is the acceptance gate for macOS x64 and
Windows x64.
When `node`, `npx`, and OpenCode are available, also run a temporary project and
global skills.sh installation smoke test pinned to the release candidate tag.

## Review Gates

- Tests must fail before launcher/build behavior is added and pass afterward.
- No default test may download a runtime archive or invoke a model provider.
- No release may publish unless all three extracted platform archives pass
  layout, safety, and grammar smoke.
- Inspect stdout/stderr and exit-code propagation from frozen and wrapped CLIs.
- Verify no optional vector/model package appears in the bundle build input.
- Verify documentation pairs remain contract-equivalent.
- Run `trellis-check` before completion and reconcile every verified finding.

## Risky Files And Rollback Points

- `skills/wiki/SKILL.md`: workflow regressions affect every supported Agent;
  preserve one source and retain all existing evidence-stage requirements.
- Bootstrap scripts: network, filesystem, and process forwarding are security
  boundaries; use version-pinned HTTPS, strict digest parsing, user-owned cache
  paths, and atomic publication only.
- PyInstaller configuration: dynamic imports can be omitted silently; native
  JavaScript/TypeScript smoke tests are the rollback gate.
- Archive handling: extraction adds traversal and link hazards absent from a
  single-file payload; member validation must happen before any extraction.
- Release workflow: permissions must be minimal and publishing tag-gated; keep
  build/test separate from release publication.
- Version metadata: reject drift in tests rather than adding compatibility
  aliases. Roll back the release metadata and Skill together if a tag is bad.
