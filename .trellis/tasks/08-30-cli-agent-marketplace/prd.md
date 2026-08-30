# Package CLI for agent marketplaces

## Goal

Let users install the Repo Dive `wiki` Skill from skills.sh and use it in
OpenCode without separately installing Python or the CLI's native Tree-sitter
dependencies.

## Confirmed Facts

- The repository already owns one portable Agent Skill at `skills/wiki/` and
  supports project-scoped discovery by OpenCode through `.agents/skills/wiki`.
- The skills.sh `npx skills` client copies or symlinks Skill contents but does
  not provide a cross-host executable installation hook.
- OpenCode discovers project Skills from `.agents/skills/` and global Skills
  from `~/.config/opencode/skills/` as installed by `npx skills`.
- The current Skill deliberately treats `repo-dive` as a separately installed
  executable and stops when it is absent from `PATH`.
- The Python package requires Python 3.11+ and native Tree-sitter wheels. A
  self-contained directory bundle can carry the interpreter, application, and
  native libraries, but release artifacts remain platform- and
  architecture-specific.
- `colbymchenry/codegraph` validates the distribution shape: a small Agent
  integration invokes a versioned platform archive that carries its application,
  language runtime, native parser, and portable parser fallback. Repo Dive will
  use the same separation without adopting CodeGraph's Node or MCP runtime.
- The public skills.sh source and GitHub Release repository is
  `https://github.com/sjin66/repo-dive`.

## Requirements

- **R1: Self-contained CLI.** Publish platform directory archives containing the
  Repo Dive launcher, Python runtime, application modules, `tree-sitter`,
  `tree-sitter-javascript`, and `tree-sitter-typescript`. End users must not need
  Python, pip, or a compiler.
- **R2: Supported targets.** The first release supports macOS ARM64, macOS x64,
  and Windows x64. Other targets must fail before downloading an artifact.
- **R3: Consent and integrity.** If no compatible CLI is already available, the
  Skill must obtain explicit user consent before installing the matching
  versioned archive. The installer must verify its published SHA-256 digest,
  reject unsafe archive entries, extract and publish the complete directory
  atomically into a user cache, and reuse the verified installation.
- **R4: Small portable Skill.** Keep a single authoritative `skills/wiki/`
  source and do not store every platform binary in the Skill or maintain
  divergent host-specific instructions.
- **R5: OpenCode support.** Support both project and global skills.sh installs,
  OpenCode's native `skill` discovery, and launcher invocation without assuming
  the installed Skill directory is writable.
- **R6: Stable behavior.** Preserve the documented non-interactive JSON/stdout,
  diagnostics/stderr, exit-code, local-artifact, and no-implicit-model contracts.
- **R7: Release lifecycle.** Tie Skill metadata and runtime archives to one
  release version; document install, first use, upgrade, cache removal,
  uninstall, unsupported-target, and failed-verification behavior.
- **R8: Existing installs.** Preserve source/wheel CLI installation and the
  existing multi-Agent project Skill installer.
- **R9: Default feature set.** Include lexical and structural retrieval but not
  optional `sentence-transformers` or model files in default bundles.
- **R10: MVP provenance.** Publish GitHub artifact attestations and checksums.
  OS vendor signing is not a first-release blocker.

## Acceptance Criteria

- [ ] **AC1 (R1, R2, R6, R9):** Native release smoke tests extract each public
      archive, run its bundled CLI, and parse JavaScript and TypeScript without
      fallback on clean macOS ARM64, macOS x64, and Windows x64 runners with no
      external Python installation.
- [ ] **AC2 (R3, R7):** A missing cache never triggers an implicit download;
      after explicit install consent, the launcher downloads the exact release
      archive, rejects checksum mismatch, traversal, absolute-path, and unsafe
      link entries, publishes only a complete smoke-tested directory atomically,
      and reuses it.
- [ ] **AC3 (R2):** Linux, Windows ARM64, and unknown targets produce an
      actionable unsupported-platform diagnostic before network access.
- [ ] **AC4 (R4, R5):** `npx skills add sjin66/repo-dive --skill wiki -a
      opencode` installs one valid Skill that OpenCode can discover from its
      documented project path; global installation is also documented and
      contract-tested.
- [ ] **AC5 (R5, R6):** The Skill's launcher forwards arguments, stdin, stdout,
      stderr, and the executable exit status without changing the CLI's JSON
      contract.
- [ ] **AC6 (R7, R10):** A tagged release contains the two named macOS `.tar.gz`
      archives, the Windows `.zip` archive, a SHA-256 manifest, and GitHub
      attestations, with package, Skill, plugin, and release versions checked for
      consistency.
- [ ] **AC7 (R7):** English and Simplified Chinese documentation provide
      equivalent installation, consent, upgrade, cache removal, uninstall,
      unsupported-target, integrity-failure, and unsigned-MVP guidance.
- [ ] **AC8 (R7, R8):** Removing the Skill or cached runtime directory does not
      remove `.repo-dive/` artifacts or unrelated files, and existing wheel/source and
      `repo-dive init` tests continue to pass.
- [ ] **AC9:** `make check` and `make test-all` pass.

## Out of Scope

- Bundling a generative model or invoking one from the CLI.
- Bundling optional `sentence-transformers` models in the default executable.
- Cloning a target repository without separate user authorization.
- Maintaining separate operational Skill instructions for each Agent host.
- Linux, Windows ARM64, and native Linux runtime archives in the first
  release.
- Bundling release binaries directly into the Skill repository.
- Publishing a PyInstaller one-file executable; platform releases use an
  inspectable directory archive.
- An OpenCode JavaScript/TypeScript plugin; OpenCode uses native Agent Skills.
- macOS notarization and Windows Authenticode signing in the checksummed MVP.

## Risks And Deferred Items

- Unsigned binaries may produce Gatekeeper or SmartScreen unknown-publisher
  warnings under some host policies. Vendor signing can be added later when
  certificate credentials are available.
- skills.sh listing/ranking is controlled by third-party indexing and telemetry;
  the deliverable guarantees standards-compliant public installation, not a
  particular leaderboard position.
