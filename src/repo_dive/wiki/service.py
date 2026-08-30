"""Application service for strict Wiki structure and resumable status."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from repo_dive.classification import (
    ClassificationResult,
    ClassificationService,
    snapshot_from_published_index,
)
from repo_dive.context import EvidenceBundle, EvidencePacker
from repo_dive.context.packer import RequiredEvidenceBudgetError
from repo_dive.errors import InvocationError, RepositoryError
from repo_dive.indexing.bm25 import tokenize_code
from repo_dive.indexing.service import PublishedIndex, load_published_index
from repo_dive.indexing.store import INDEX_SCHEMA_VERSION, IndexStore
from repo_dive.parsing.models import Chunk, Symbol
from repo_dive.retrieval.fusion import FusionMetadata, SearchHit
from repo_dive.retrieval.service import search_repository
from repo_dive.schema import JsonObject, JsonValue
from repo_dive.wiki.assembler import WikiBuildContext, assemble_wiki
from repo_dive.wiki.legacy import has_legacy_state
from repo_dive.wiki.models import (
    METADATA_SCHEMA_VERSION,
    EvidenceRef,
    EvidenceSnapshot,
    Metadata,
    Page,
    PageStatus,
    RetrievalParameters,
    Section,
    Subsection,
    Wiki,
)
from repo_dive.wiki.store import WIKI_MARKDOWN_PATH, WikiStore
from repo_dive.wiki.submission import PageSubmission, validate_submission_content
from repo_dive.wiki.templates import (
    ComposedContract,
    compose_template,
)
from repo_dive.wiki.templates.models import ContractNode, TemplateIdentity
from repo_dive.wiki.validation import (
    stale_page_ids_for_index,
    validate_page_evidence,
)

STRUCTURE_SCHEMA_VERSION = "2.0"
MAX_EVIDENCE_QUERY_LENGTH = 1_000

_FRAMEWORK_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "contents": "Contents",
        "related_pages": "Related pages",
        "sources": "Sources",
        "scope_version": "Scope and version",
        "scan_mode": "Scan mode",
        "git_scope": "Git corpus",
        "git_scope_description": (
            "tracked plus unignored untracked files after the recorded filters"
        ),
        "include_patterns": "Include patterns",
        "exclude_patterns": "Exclude patterns",
        "default_exclusions": "Default excluded directories",
        "indexed_files": "Indexed files",
        "skipped_files": "Skipped files",
        "index_build": "Index build",
        "repository_fingerprint": "Repository fingerprint",
        "source_commit": "Source commit",
        "source_state": "Source state",
        "source_state_clean": "clean",
        "source_state_dirty": "dirty",
        "source_state_non_git": "non-Git",
        "source_commit_none": "none",
        "patterns_none": "none",
        "generated_at": "Generated at",
    },
    "zh-CN": {
        "contents": "目录",
        "related_pages": "相关页面",
        "sources": "来源",
        "scope_version": "范围与版本",
        "scan_mode": "扫描模式",
        "git_scope": "Git 语料库",
        "git_scope_description": "应用已记录过滤器后的已跟踪及未忽略未跟踪文件",
        "include_patterns": "包含模式",
        "exclude_patterns": "排除模式",
        "default_exclusions": "默认排除目录",
        "indexed_files": "已索引文件",
        "skipped_files": "已跳过文件",
        "index_build": "索引构建",
        "repository_fingerprint": "代码库指纹",
        "source_commit": "源提交",
        "source_state": "源状态",
        "source_state_clean": "干净",
        "source_state_dirty": "有未提交更改",
        "source_state_non_git": "非 Git",
        "source_commit_none": "无",
        "patterns_none": "无",
        "generated_at": "生成时间",
    },
    "ja": {
        "contents": "目次",
        "related_pages": "関連ページ",
        "sources": "出典",
        "scope_version": "スコープとバージョン",
        "scan_mode": "スキャンモード",
        "git_scope": "Git コーパス",
        "git_scope_description": (
            "記録されたフィルター適用後の追跡済みファイルと無視されていない未追跡ファイル"
        ),
        "include_patterns": "包含パターン",
        "exclude_patterns": "除外パターン",
        "default_exclusions": "既定の除外ディレクトリ",
        "indexed_files": "索引済みファイル",
        "skipped_files": "スキップしたファイル",
        "index_build": "インデックスビルド",
        "repository_fingerprint": "リポジトリ指紋",
        "source_commit": "ソースコミット",
        "source_state": "ソース状態",
        "source_state_clean": "クリーン",
        "source_state_dirty": "変更あり",
        "source_state_non_git": "Git 以外",
        "source_commit_none": "なし",
        "patterns_none": "なし",
        "generated_at": "生成日時",
    },
}

_WIKI_DESCRIPTIONS = {
    "en": "Evidence-grounded repository documentation.",
    "zh-CN": "基于代码库证据的文档。",
    "ja": "リポジトリの根拠に基づくドキュメント。",
}


@dataclass(frozen=True, slots=True)
class StructurePage:
    """Caller-owned structural fields for one page, excluding persisted state."""

    id: str
    title: str
    description: str
    relevant_files: tuple[str, ...]
    related_page_ids: tuple[str, ...]
    subsections: tuple[Subsection, ...]

    def to_pending_page(self) -> Page:
        """Validate structure through the canonical persisted Page model."""
        return Page(
            id=self.id,
            title=self.title,
            description=self.description,
            status=PageStatus.PENDING,
            relevant_files=self.relevant_files,
            related_page_ids=self.related_page_ids,
            subsections=self.subsections,
        )


@dataclass(frozen=True, slots=True)
class StructureSection:
    """Caller-owned ordered section structure."""

    id: str
    title: str
    pages: tuple[StructurePage, ...]

    def to_pending_section(self) -> Section:
        return Section(
            id=self.id,
            title=self.title,
            pages=tuple(page.to_pending_page() for page in self.pages),
        )


@dataclass(frozen=True, slots=True)
class WikiStructure:
    """Strict external structure proposal without mutable lifecycle fields."""

    title: str
    description: str
    output_language: str
    sections: tuple[StructureSection, ...]
    schema_version: str = STRUCTURE_SCHEMA_VERSION
    framework_labels: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != STRUCTURE_SCHEMA_VERSION:
            raise ValueError("Wiki structure schema version is not supported")
        if self.output_language not in _FRAMEWORK_LABELS:
            raise ValueError("output language must be one of en, zh-CN, or ja")
        if self.framework_labels and set(dict(self.framework_labels)) != set(
            _FRAMEWORK_LABELS[self.output_language]
        ):
            raise ValueError("framework locale labels are incomplete or unexpected")
        self.to_pending_wiki()

    def to_pending_wiki(self) -> Wiki:
        return Wiki(
            title=self.title,
            description=self.description,
            sections=tuple(section.to_pending_section() for section in self.sections),
            framework_labels=(
                self.framework_labels
                or tuple(sorted(_FRAMEWORK_LABELS[self.output_language].items()))
            ),
        )


@dataclass(frozen=True, slots=True)
class StructureUpdate:
    """Observable outcome of applying one validated structure proposal."""

    changed: bool
    created_page_ids: tuple[str, ...]
    invalidated_page_ids: tuple[str, ...]
    preserved_page_ids: tuple[str, ...]
    wiki: Wiki
    metadata: Metadata


@dataclass(frozen=True, slots=True)
class WikiState:
    """A complete, mutually present Wiki and metadata snapshot."""

    wiki: Wiki
    metadata: Metadata


@dataclass(frozen=True, slots=True)
class WikiEvidenceUpdate:
    """Persisted page Evidence plus complete source output for the caller."""

    page: Page
    bundle: EvidenceBundle
    fusion: FusionMetadata
    symbols: tuple[Symbol, ...]
    metadata: Metadata


@dataclass(frozen=True, slots=True)
class WikiPageUpdate:
    """Observable outcome of persisting one generated Wiki page."""

    changed: bool
    page: Page
    metadata: Metadata


@dataclass(frozen=True, slots=True)
class WikiBuildUpdate:
    """Complete assembled Markdown plus its atomic persistence outcome."""

    changed: bool
    markdown: str
    artifact_path: str
    wiki: Wiki
    metadata: Metadata


class WikiService:
    """Validate, merge, persist, and inspect repository-owned Wiki state."""

    def __init__(
        self,
        repository: str | Path,
        *,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._store = WikiStore(repository)
        self._clock = clock or _utc_now

    def apply_structure(self, structure: WikiStructure) -> StructureUpdate:
        """Apply a structure while preserving state for unaffected Page IDs."""
        published = load_published_index(self._store.repository)
        proposed = structure.to_pending_wiki()
        _validate_relevant_files(proposed, published)
        current = self._read_optional_state()
        now = self._clock()

        if current is None:
            metadata = _new_metadata(
                published,
                output_language=structure.output_language,
                timestamp=now,
            )
            self._store.write_metadata(metadata)
            self._store.write_wiki(proposed)
            return StructureUpdate(
                changed=True,
                created_page_ids=_page_ids(proposed),
                invalidated_page_ids=(),
                preserved_page_ids=(),
                wiki=proposed,
                metadata=metadata,
            )

        language_changed = current.metadata.output_language != structure.output_language
        source_identity_changed = (
            current.metadata.source_control != published.manifest.source_control
            or current.metadata.source_commit != published.manifest.source_commit
            or current.metadata.source_dirty != published.manifest.source_dirty
        )
        index_changed = (
            current.metadata.repository_fingerprint
            != published.manifest.repository_fingerprint
            or current.metadata.index_build_id != published.manifest.build_id
            or current.metadata.index_schema_version != INDEX_SCHEMA_VERSION
        )
        stale_ids = (
            frozenset(stale_page_ids_for_index(published, current.wiki))
            if index_changed
            else frozenset()
        )
        merged, created, invalidated, preserved = _merge_wiki(
            current.wiki,
            proposed,
            stale_page_ids=stale_ids,
            invalidate_all=language_changed or source_identity_changed,
        )
        metadata_changed = (
            current.metadata.repository != str(published.repository)
            or current.metadata.repository_fingerprint
            != published.manifest.repository_fingerprint
            or current.metadata.output_language != structure.output_language
            or current.metadata.index_schema_version != INDEX_SCHEMA_VERSION
            or current.metadata.index_build_id != published.manifest.build_id
            or current.metadata.source_control != published.manifest.source_control
            or current.metadata.source_commit != published.manifest.source_commit
            or current.metadata.source_dirty != published.manifest.source_dirty
        )
        changed = merged != current.wiki or metadata_changed
        if not changed:
            return StructureUpdate(
                changed=False,
                created_page_ids=(),
                invalidated_page_ids=(),
                preserved_page_ids=_page_ids(current.wiki),
                wiki=current.wiki,
                metadata=current.metadata,
            )

        metadata = replace(
            current.metadata,
            repository=str(published.repository),
            repository_fingerprint=published.manifest.repository_fingerprint,
            output_language=structure.output_language,
            index_schema_version=INDEX_SCHEMA_VERSION,
            index_build_id=published.manifest.build_id,
            source_control=published.manifest.source_control,
            source_commit=published.manifest.source_commit,
            source_dirty=published.manifest.source_dirty,
            updated_at=now,
        )
        self._store.write_metadata(metadata)
        self._store.write_wiki(merged)
        return StructureUpdate(
            changed=True,
            created_page_ids=created,
            invalidated_page_ids=invalidated,
            preserved_page_ids=preserved,
            wiki=merged,
            metadata=metadata,
        )

    def initialize(self, structure: WikiStructure) -> StructureUpdate:
        """Explicitly replace Wiki JSON state while preserving published Markdown."""
        if not has_legacy_state(self._store.repository):
            current = self._read_optional_state()
            if current is not None:
                return self.apply_structure(structure)
        published = load_published_index(self._store.repository)
        proposed = structure.to_pending_wiki()
        _validate_relevant_files(proposed, published)
        now = self._clock()
        metadata = _new_metadata(
            published, output_language=structure.output_language, timestamp=now
        )
        self._store.write_metadata(metadata)
        self._store.write_wiki(proposed)
        return StructureUpdate(
            changed=True,
            created_page_ids=_page_ids(proposed),
            invalidated_page_ids=(),
            preserved_page_ids=(),
            wiki=proposed,
            metadata=metadata,
        )

    def classify(self, *, template_override: str | None = None) -> ClassificationResult:
        """Classify the current published index without mutating Wiki state."""
        published = load_published_index(self._store.repository)
        return _classify_published(published, template_override=template_override)

    def initialize_governed(
        self, *, locale: str, template_override: str | None = None
    ) -> StructureUpdate:
        """Compose and persist the exact localized built-in Wiki contract."""
        published = load_published_index(self._store.repository)
        classification = _classify_published(
            published, template_override=template_override
        )
        contract = compose_template(
            classification.effective_primary.id,
            classification.topology.id,
            tuple(item.id for item in classification.facets),
            locale,
        )
        structure = _structure_from_contract(published, contract)
        proposed = structure.to_pending_wiki()
        _validate_relevant_files(proposed, published)
        now = self._clock()
        metadata = _new_metadata(
            published,
            output_language=locale,
            timestamp=now,
            classification=classification,
            template=contract.identity,
        )

        current = (
            None
            if has_legacy_state(self._store.repository)
            else self._read_optional_state()
        )
        if current is not None and current.metadata.template == contract.identity:
            source_identity_changed = (
                current.metadata.source_control != published.manifest.source_control
                or current.metadata.source_commit != published.manifest.source_commit
                or current.metadata.source_dirty != published.manifest.source_dirty
            )
            index_changed = (
                current.metadata.repository_fingerprint
                != published.manifest.repository_fingerprint
                or current.metadata.index_build_id != published.manifest.build_id
            )
            stale_ids = (
                frozenset(stale_page_ids_for_index(published, current.wiki))
                if index_changed
                else frozenset()
            )
            merged, created, invalidated, preserved = _merge_wiki(
                current.wiki,
                proposed,
                stale_page_ids=stale_ids,
                invalidate_all=source_identity_changed,
            )
            metadata_changed = (
                current.metadata.repository_classification != classification
                or current.metadata.repository_fingerprint
                != published.manifest.repository_fingerprint
                or current.metadata.index_build_id != published.manifest.build_id
                or current.metadata.source_control != published.manifest.source_control
                or current.metadata.source_commit != published.manifest.source_commit
                or current.metadata.source_dirty != published.manifest.source_dirty
            )
            if merged == current.wiki and not metadata_changed:
                return StructureUpdate(
                    False, (), (), _page_ids(merged), merged, current.metadata
                )
            metadata = replace(
                current.metadata,
                repository_fingerprint=published.manifest.repository_fingerprint,
                index_build_id=published.manifest.build_id,
                source_control=published.manifest.source_control,
                source_commit=published.manifest.source_commit,
                source_dirty=published.manifest.source_dirty,
                repository_classification=classification,
                updated_at=now,
            )
            self._store.write_metadata(metadata)
            self._store.write_wiki(merged)
            return StructureUpdate(
                True, created, invalidated, preserved, merged, metadata
            )
        self._store.write_metadata(metadata)
        self._store.write_wiki(proposed)
        return StructureUpdate(
            changed=True,
            created_page_ids=_page_ids(proposed),
            invalidated_page_ids=(),
            preserved_page_ids=(),
            wiki=proposed,
            metadata=metadata,
        )

    def read_state(self) -> WikiState:
        """Read a complete initialized state or return a stable repository error."""
        state = self._read_optional_state()
        if state is None:
            raise RepositoryError(
                "wiki_not_initialized",
                "Repository Wiki has not been initialized.",
            )
        expected_labels = _expected_framework_labels(state.metadata)
        if (
            expected_labels is None
            or dict(state.wiki.framework_labels) != expected_labels
        ):
            raise RepositoryError(
                "wiki_state_invalid",
                "Repository Wiki locale labels do not match its persisted locale.",
            )
        if state.metadata.template is not None:
            template = state.metadata.template
            current_identity = compose_template(
                template.primary_id,
                template.topology_id,
                template.facets,
                template.locale,
            ).identity
            if current_identity != template:
                raise RepositoryError(
                    "wiki_template_state_stale",
                    "Persisted Wiki template identity does not match the "
                    "built-in registry.",
                )
        return state

    def collect_evidence(
        self,
        page_id: str,
        *,
        token_budget: int,
        max_results: int,
    ) -> WikiEvidenceUpdate:
        """Retrieve, persist, then return one page's complete Evidence bundle."""
        state = self.read_state()
        page = _find_page(state.wiki, page_id)
        if page is None:
            raise InvocationError(
                "wiki_page_unknown",
                "Wiki page ID does not exist in the current structure.",
                details={"page_id": page_id},
            )

        try:
            query = _evidence_query(page)
            retrieved = search_repository(
                self._store.repository,
                query,
                max_results=max_results,
            )
            published = load_published_index(self._store.repository)
            if retrieved.build_id != published.manifest.build_id:
                raise RepositoryError(
                    "index_changed_during_operation",
                    "Repository index changed while Evidence was being collected.",
                )
            required_hits, coverage = _direct_evidence_hits(
                page, published, retrieved.fusion.hits
            )
            try:
                bundle = EvidencePacker().pack(
                    query,
                    retrieved.fusion.hits,
                    token_budget=token_budget,
                    required_hits=required_hits,
                )
            except RequiredEvidenceBudgetError as error:
                raise RepositoryError(
                    "wiki_evidence_direct_budget_insufficient",
                    "The complete required direct Evidence does not fit the budget.",
                    details={
                        "page_id": page.id,
                        "required_items": error.required_items,
                        "required_minimum_tokens": error.required_tokens,
                    },
                ) from error
            if not bundle.items:
                raise RepositoryError(
                    "wiki_evidence_empty",
                    "No complete repository Evidence fits the page budget.",
                    details={"page_id": page_id},
                )
            stale_ids = stale_page_ids_for_index(published, state.wiki)
        except RepositoryError as error:
            if error.code != "wiki_evidence_direct_budget_insufficient":
                self._persist_failed_page(state, page_id=page_id, error_code=error.code)
            raise

        generated_at = self._clock()
        snapshot = EvidenceSnapshot(
            query=query,
            repository_fingerprint=published.manifest.repository_fingerprint,
            index_schema_version=INDEX_SCHEMA_VERSION,
            index_build_id=published.manifest.build_id,
            source_control=published.manifest.source_control,
            source_commit=published.manifest.source_commit,
            source_dirty=published.manifest.source_dirty,
            token_budget=bundle.token_budget,
            estimated_tokens=bundle.estimated_tokens,
            reserved_tokens=bundle.reserved_tokens,
            estimator=bundle.estimator,
            truncated=bundle.truncated,
            retrieval=RetrievalParameters(
                max_results=max_results,
                strategy=retrieved.fusion.metadata.strategy,
                rrf_k=retrieved.fusion.metadata.rrf_k,
                channel_weights=retrieved.fusion.metadata.channel_weights,
                overlap_threshold=retrieved.fusion.metadata.overlap_threshold,
            ),
            generated_at=generated_at,
        )
        references = tuple(
            EvidenceRef(
                evidence_id=item.evidence_id,
                chunk_id=item.hit.chunk.id,
                path=item.hit.chunk.path,
                start_line=item.hit.chunk.start_line,
                end_line=item.hit.chunk.end_line,
                content_hash=item.hit.chunk.content_hash,
                role=("direct" if item.hit.chunk.id in coverage else "supplemental"),
                subsection_ids=tuple(
                    dict.fromkeys(
                        subsection_id
                        for subsection_id, _ in coverage.get(item.hit.chunk.id, ())
                    )
                ),
                direct_paths=tuple(
                    dict.fromkeys(
                        path for _, path in coverage.get(item.hit.chunk.id, ())
                    )
                ),
            )
            for item in bundle.items
        )
        normalized = _reset_stale_pages(state.wiki, frozenset(stale_ids))
        current_page = _find_page(normalized, page_id)
        if current_page is None:  # pragma: no cover - protected by immutable IDs
            raise RuntimeError("Wiki page disappeared while collecting Evidence")
        updated_page = _with_ready_evidence(
            current_page,
            evidence=references,
            snapshot=snapshot,
        )
        updated_wiki = _replace_page(normalized, updated_page)
        metadata = _updated_metadata(
            state.metadata,
            published,
            timestamp=generated_at,
        )
        self._store.write_metadata(metadata)
        self._store.write_wiki(updated_wiki)
        return WikiEvidenceUpdate(
            page=updated_page,
            bundle=bundle,
            fusion=retrieved.fusion.metadata,
            symbols=retrieved.symbols,
            metadata=metadata,
        )

    def submit_page(
        self,
        page_id: str,
        submission: PageSubmission,
    ) -> WikiPageUpdate:
        """Validate and atomically persist one agent-generated page."""
        state = self.read_state()
        page = _find_page(state.wiki, page_id)
        if page is None:
            raise InvocationError(
                "wiki_page_unknown",
                "Wiki page ID does not exist in the current structure.",
                details={"page_id": page_id},
            )
        if submission.page_id != page_id:
            raise InvocationError(
                "wiki_page_id_mismatch",
                "Wiki page input does not match the requested Page ID.",
                details={"page_id": page_id},
            )
        if page.status not in {
            PageStatus.EVIDENCE_READY,
            PageStatus.FAILED,
            PageStatus.GENERATED,
        }:
            raise InvocationError(
                "wiki_page_state_invalid",
                "Wiki page is not ready for generated content.",
                details={"page_id": page_id, "status": page.status.value},
            )

        validate_page_evidence(self._store.repository, page)
        if page.status is PageStatus.GENERATED:
            if page.subsection_contents == submission.subsections:
                return WikiPageUpdate(
                    changed=False,
                    page=page,
                    metadata=state.metadata,
                )
            raise InvocationError(
                "wiki_page_state_invalid",
                "Generated Wiki pages cannot be replaced by page submission.",
                details={"page_id": page_id, "status": page.status.value},
            )

        validate_submission_content(page, submission)

        generated = _with_generated_content(page, submission)
        timestamp = self._clock()
        metadata = replace(state.metadata, updated_at=timestamp)
        self._store.write_metadata(metadata)
        self._store.write_wiki(_replace_page(state.wiki, generated))
        return WikiPageUpdate(changed=True, page=generated, metadata=metadata)

    def build_wiki(self) -> WikiBuildUpdate:
        """Validate all page Evidence, assemble, and atomically publish Markdown."""
        state = self.read_state()
        pages = tuple(page for section in state.wiki.sections for page in section.pages)
        incomplete = tuple(
            page.id for page in pages if page.status is not PageStatus.GENERATED
        )
        if incomplete:
            raise RepositoryError(
                "wiki_build_incomplete",
                "Wiki cannot be built until every page is generated.",
                details={"page_ids": list(incomplete)},
            )
        invalid = tuple(
            page.id
            for page in pages
            if not page.subsection_contents or not page.citation_ids
        )
        if invalid:
            raise RepositoryError(
                "wiki_build_page_invalid",
                "Generated Wiki pages are missing body or citation data.",
                details={"page_ids": list(invalid)},
            )
        published = load_published_index(self._store.repository)
        stale = stale_page_ids_for_index(published, state.wiki)
        if stale:
            raise RepositoryError(
                "wiki_evidence_stale",
                "Wiki page Evidence is stale for the current repository index.",
                details={"page_ids": list(stale)},
            )
        _validate_state_index_identity(state, published)

        context = _build_context(state, published)
        markdown = assemble_wiki(state.wiki, context)
        current = load_published_index(self._store.repository)
        if current.manifest != published.manifest:
            raise RepositoryError(
                "index_changed_during_operation",
                "Repository index changed while Wiki Markdown was being assembled.",
            )
        _, changed = self._store.write_markdown(markdown)
        return WikiBuildUpdate(
            changed=changed,
            markdown=markdown,
            artifact_path=WIKI_MARKDOWN_PATH,
            wiki=state.wiki,
            metadata=state.metadata,
        )

    def validate_wiki(self) -> WikiState:
        """Validate persisted Schema 2.0 contracts without publishing Markdown."""
        state = self.read_state()
        if state.metadata.template is None:
            raise InvocationError(
                "wiki_validation_failed",
                "Wiki validation requires template-governed Schema 2.0 state.",
            )
        incomplete = tuple(
            page.id
            for section in state.wiki.sections
            for page in section.pages
            if page.status is not PageStatus.GENERATED
        )
        if incomplete:
            raise InvocationError(
                "wiki_validation_failed",
                "Wiki validation requires every Page to be generated.",
                details={"page_ids": list(incomplete)},
            )
        for section in state.wiki.sections:
            for page in section.pages:
                validate_page_evidence(self._store.repository, page)
                validate_submission_content(
                    page,
                    PageSubmission(
                        page_id=page.id,
                        subsections=page.subsection_contents,
                    ),
                )
        published = load_published_index(self._store.repository)
        _validate_state_index_identity(state, published)
        assemble_wiki(state.wiki, _build_context(state, published))
        if load_published_index(self._store.repository).manifest != published.manifest:
            raise RepositoryError(
                "index_changed_during_operation",
                "Repository index changed while Wiki state was being validated.",
            )
        return state

    def _persist_failed_page(
        self,
        state: WikiState,
        *,
        page_id: str,
        error_code: str,
    ) -> None:
        page = _find_page(state.wiki, page_id)
        if page is None:
            return
        failed = (
            page
            if page.status is PageStatus.FAILED
            else page.transition_to(PageStatus.FAILED)
        )
        failed = replace(failed, error=error_code)
        timestamp = self._clock()
        self._store.write_metadata(replace(state.metadata, updated_at=timestamp))
        self._store.write_wiki(_replace_page(state.wiki, failed))

    def _read_optional_state(self) -> WikiState | None:
        has_wiki = self._store.has_wiki()
        has_metadata = self._store.has_metadata()
        if not has_wiki and not has_metadata:
            return None
        if has_wiki != has_metadata:
            raise RepositoryError(
                "wiki_state_incomplete",
                "Repository Wiki state is incomplete.",
            )
        return WikiState(
            wiki=self._store.read_wiki(),
            metadata=self._store.read_metadata(),
        )


def structure_from_document(document: JsonObject) -> WikiStructure:
    """Strictly decode a caller-provided stateless Wiki structure."""
    _require_fields(
        document,
        {
            "description",
            "output_language",
            "schema_version",
            "sections",
            "title",
        },
        "Wiki structure fields",
    )
    schema_version = _string(document["schema_version"])
    if schema_version != STRUCTURE_SCHEMA_VERSION:
        raise ValueError("Wiki structure schema version is not supported")
    return WikiStructure(
        title=_string(document["title"]),
        description=_string(document["description"]),
        output_language=_string(document["output_language"]),
        sections=tuple(
            _section_from_document(_object(item))
            for item in _array(document["sections"])
        ),
        schema_version=schema_version,
    )


def _classify_published(
    published: PublishedIndex, *, template_override: str | None
) -> ClassificationResult:
    snapshot = snapshot_from_published_index(published)
    return ClassificationService().classify(snapshot, override=template_override)


def _expected_framework_labels(metadata: Metadata) -> dict[str, str] | None:
    if metadata.template is None:
        return _FRAMEWORK_LABELS.get(metadata.output_language)
    template = metadata.template
    contract = compose_template(
        template.primary_id,
        template.topology_id,
        template.facets,
        template.locale,
    )
    labels = dict(contract.labels)
    return {key: labels[key] for key in _FRAMEWORK_LABELS[template.locale]}


def _build_context(state: WikiState, published: PublishedIndex) -> WikiBuildContext:
    manifest = published.manifest
    return WikiBuildContext(
        scan_mode=manifest.scan_mode,
        include=manifest.parameters.include,
        exclude=manifest.parameters.exclude,
        effective_default_excluded_directories=(
            manifest.effective_default_excluded_directories
        ),
        indexed_files=manifest.counts.indexed_files,
        skipped_files=manifest.counts.skipped_files,
        index_build_id=manifest.build_id,
        repository_fingerprint=manifest.repository_fingerprint,
        source_control=manifest.source_control,
        source_commit=manifest.source_commit,
        source_dirty=manifest.source_dirty,
        generated_at=state.metadata.updated_at,
    )


def _validate_state_index_identity(state: WikiState, published: PublishedIndex) -> None:
    manifest = published.manifest
    expected_metadata = (
        manifest.build_id,
        manifest.repository_fingerprint,
        manifest.source_control,
        manifest.source_commit,
        manifest.source_dirty,
    )
    metadata_identity = (
        state.metadata.index_build_id,
        state.metadata.repository_fingerprint,
        state.metadata.source_control,
        state.metadata.source_commit,
        state.metadata.source_dirty,
    )
    expected_source = (
        manifest.source_control,
        manifest.source_commit,
        manifest.source_dirty,
    )
    snapshots_match = all(
        page.evidence_snapshot is not None
        and (
            page.evidence_snapshot.source_control,
            page.evidence_snapshot.source_commit,
            page.evidence_snapshot.source_dirty,
        )
        == expected_source
        for section in state.wiki.sections
        for page in section.pages
    )
    if metadata_identity != expected_metadata or not snapshots_match:
        raise RepositoryError(
            "wiki_evidence_stale",
            "Wiki Evidence identity does not match the current published index.",
            details={"page_ids": list(_page_ids(state.wiki))},
        )


def _structure_from_contract(
    published: PublishedIndex, contract: ComposedContract
) -> WikiStructure:
    labels = dict(contract.labels)
    subsection_descriptions = dict(contract.subsection_descriptions)
    chunks = _governed_chunks(published)
    sections: list[StructureSection] = []
    for section_node in (
        node
        for root in contract.nodes
        for node in root.walk()
        if node.node_type == "section"
    ):
        page_nodes = tuple(
            node
            for child in section_node.children
            for node in child.walk()
            if node.node_type == "page"
        )
        if not page_nodes:
            continue
        pages = tuple(
            _structure_page_from_contract(
                node,
                labels,
                subsection_descriptions,
                chunks,
            )
            for node in page_nodes
            if not _is_unsupported_extension_page(node, chunks)
        )
        if not pages:
            continue
        sections.append(
            StructureSection(
                section_node.logical_id, labels[section_node.logical_id], pages
            )
        )
    if not sections:
        raise RepositoryError(
            "wiki_template_structure_invalid",
            "The composed Wiki template does not contain any Pages.",
        )
    return WikiStructure(
        title=f"{published.repository.name} Wiki",
        description=_WIKI_DESCRIPTIONS[contract.identity.locale],
        output_language=contract.identity.locale,
        sections=tuple(sections),
        framework_labels=tuple(
            sorted(
                (key, labels[key])
                for key in _FRAMEWORK_LABELS[contract.identity.locale]
            )
        ),
    )


def _structure_page_from_contract(
    page_node: ContractNode,
    labels: dict[str, str],
    subsection_descriptions: dict[str, str],
    chunks: tuple[Chunk, ...],
) -> StructurePage:
    subsection_nodes = tuple(
        node for node in page_node.children if node.node_type == "subsection"
    )
    if not subsection_nodes:
        raise RepositoryError(
            "wiki_template_structure_invalid",
            "Every governed Wiki Page must contain a Subsection.",
            details={"page_id": page_node.logical_id},
        )
    extension_paths = (
        _extension_boundary_paths(chunks)
        if page_node.logical_id in _EVIDENCE_GATED_EXTENSION_PAGE_IDS
        else ()
    )
    subsections = tuple(
        _subsection_from_contract(
            page_node,
            node,
            labels,
            subsection_descriptions,
            chunks,
            focused_paths=extension_paths,
        )
        for node in subsection_nodes
    )
    relevant_files = tuple(
        dict.fromkeys(
            path
            for subsection in subsections
            for path in subsection.direct_source_paths
        )
    )
    return StructurePage(
        id=page_node.logical_id,
        title=labels[page_node.logical_id],
        description=labels[page_node.logical_id],
        relevant_files=relevant_files,
        related_page_ids=(),
        subsections=subsections,
    )


def _governed_chunks(published: PublishedIndex) -> tuple[Chunk, ...]:
    with IndexStore.open_readonly(published.database) as store:
        chunks = store.get_chunks()
    if not chunks:
        raise RepositoryError(
            "wiki_direct_source_unavailable",
            "The current index does not contain a complete Chunk for Wiki Evidence.",
        )
    return chunks


def _subsection_from_contract(
    page_node: ContractNode,
    subsection_node: ContractNode,
    labels: dict[str, str],
    subsection_descriptions: dict[str, str],
    chunks: tuple[Chunk, ...],
    *,
    focused_paths: tuple[str, ...] = (),
) -> Subsection:
    title = labels[subsection_node.logical_id]
    page_title = labels[page_node.logical_id]
    query_terms = frozenset(
        tokenize_code(
            f"{page_node.logical_id} {subsection_node.logical_id} {page_title} {title}"
        )
    )
    ranked = sorted(
        chunks,
        key=lambda chunk: (
            -_chunk_relevance(chunk, query_terms),
            chunk.symbol_id is None,
            _is_documentation_path(chunk.path),
            chunk.path,
            chunk.start_line,
            chunk.id,
        ),
    )
    return Subsection(
        id=subsection_node.logical_id,
        title=title,
        description=subsection_descriptions[subsection_node.logical_id],
        direct_source_paths=focused_paths or (ranked[0].path,),
        documentation_only=False,
    )


def _chunk_relevance(chunk: Chunk, query_terms: frozenset[str]) -> int:
    chunk_terms = frozenset(tokenize_code(f"{chunk.path} {chunk.text}"))
    return len(query_terms & chunk_terms)


def _is_unsupported_extension_page(
    page_node: ContractNode, chunks: tuple[Chunk, ...]
) -> bool:
    if page_node.logical_id not in _EVIDENCE_GATED_EXTENSION_PAGE_IDS:
        return False
    return not _extension_boundary_paths(chunks)


_EXTENSION_BOUNDARY_PATTERNS = (
    re.compile(
        r"\A[ \t]*class\s+ParserAdapter\s*\(\s*Protocol\s*\)\s*:"
        r".*?^[ \t]+def\s+parse\s*\(",
        re.MULTILINE | re.S,
    ),
    re.compile(
        r"\A[ \t]*class\s+[A-Za-z_][A-Za-z0-9_]*Provider"
        r"\s*\(\s*Protocol\s*\)\s*:.*?^[ \t]+def\s+embed\s*\(",
        re.MULTILINE | re.S,
    ),
    re.compile(
        r"\A[ \t]*class\s+[A-Za-z_][A-Za-z0-9_]*Retriever"
        r"\s*\(\s*Protocol\s*\)\s*:.*?^[ \t]+def\s+retrieve\s*\(",
        re.MULTILINE | re.S,
    ),
)

_EVIDENCE_GATED_EXTENSION_PAGE_IDS = frozenset(
    {"cli_extension_points_page", "tool_extension_points_page"}
)


def _extension_boundary_paths(chunks: tuple[Chunk, ...]) -> tuple[str, ...]:
    """Return paths that declare supported parser/retriever/Provider contracts."""
    return tuple(
        sorted(
            {
                chunk.path
                for chunk in chunks
                if any(
                    pattern.search(chunk.text)
                    for pattern in _EXTENSION_BOUNDARY_PATTERNS
                )
            }
        )
    )


def _is_documentation_path(path: str) -> bool:
    lowered = path.lower()
    return lowered.endswith((".md", ".mdx", ".rst", ".txt")) or lowered.startswith(
        ("docs/", "doc/")
    )


def _section_from_document(document: JsonObject) -> StructureSection:
    _require_fields(document, {"id", "pages", "title"}, "Section fields")
    return StructureSection(
        id=_string(document["id"]),
        title=_string(document["title"]),
        pages=tuple(
            _page_from_document(_object(item)) for item in _array(document["pages"])
        ),
    )


def _page_from_document(document: JsonObject) -> StructurePage:
    required = {"description", "id", "related_page_ids", "relevant_files", "title"}
    if set(document) != {*required, "subsections"}:
        raise ValueError("Page structure fields are invalid")
    relevant_files = _string_tuple(document["relevant_files"])
    subsections = tuple(
        _subsection_from_document(_object(item))
        for item in _array(document["subsections"])
    )
    return StructurePage(
        id=_string(document["id"]),
        title=_string(document["title"]),
        description=_string(document["description"]),
        relevant_files=relevant_files,
        related_page_ids=_string_tuple(document["related_page_ids"]),
        subsections=subsections,
    )


def _subsection_from_document(document: JsonObject) -> Subsection:
    _require_fields(
        document,
        {"description", "direct_source_paths", "documentation_only", "id", "title"},
        "Subsection structure fields",
    )
    return Subsection(
        id=_string(document["id"]),
        title=_string(document["title"]),
        description=_string(document["description"]),
        direct_source_paths=_string_tuple(document["direct_source_paths"]),
        documentation_only=_boolean(document["documentation_only"]),
    )


def _validate_relevant_files(wiki: Wiki, published: PublishedIndex) -> None:
    known_paths = {item.path for item in published.manifest.files}
    requested_paths = {
        path
        for section in wiki.sections
        for page in section.pages
        for path in page.relevant_files
    }
    requested_paths.update(
        path
        for section in wiki.sections
        for page in section.pages
        for subsection in page.subsections
        for path in subsection.direct_source_paths
    )
    unknown = tuple(sorted(requested_paths - known_paths))
    if unknown:
        raise InvocationError(
            "wiki_relevant_file_unknown",
            "Wiki structure references files outside the current index.",
            details={"paths": list(unknown)},
        )


def _merge_wiki(
    current: Wiki,
    proposed: Wiki,
    *,
    stale_page_ids: frozenset[str],
    invalidate_all: bool,
) -> tuple[Wiki, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    current_pages = {
        page.id: page for section in current.sections for page in section.pages
    }
    created: list[str] = []
    invalidated: list[str] = []
    preserved: list[str] = []
    sections: list[Section] = []
    for proposed_section in proposed.sections:
        pages: list[Page] = []
        for proposed_page in proposed_section.pages:
            previous = current_pages.get(proposed_page.id)
            if previous is None:
                created.append(proposed_page.id)
                pages.append(proposed_page)
            elif (
                not invalidate_all
                and proposed_page.id not in stale_page_ids
                and _same_page_structure(previous, proposed_page)
            ):
                preserved.append(proposed_page.id)
                pages.append(previous)
            else:
                invalidated.append(proposed_page.id)
                pages.append(
                    replace(
                        proposed_page,
                        status=PageStatus.PENDING,
                        evidence=previous.evidence,
                        body=previous.body,
                        error=previous.error,
                    )
                )
        sections.append(replace(proposed_section, pages=tuple(pages)))
    return (
        replace(proposed, sections=tuple(sections)),
        tuple(created),
        tuple(invalidated),
        tuple(preserved),
    )


def _same_page_structure(current: Page, proposed: Page) -> bool:
    return (
        current.id == proposed.id
        and current.title == proposed.title
        and current.description == proposed.description
        and current.relevant_files == proposed.relevant_files
        and current.related_page_ids == proposed.related_page_ids
        and current.subsections == proposed.subsections
    )


def _new_metadata(
    published: PublishedIndex,
    *,
    output_language: str,
    timestamp: str,
    classification: ClassificationResult | None = None,
    template: TemplateIdentity | None = None,
) -> Metadata:
    return Metadata(
        repository=str(published.repository),
        repository_fingerprint=published.manifest.repository_fingerprint,
        output_language=output_language,
        index_schema_version=INDEX_SCHEMA_VERSION,
        index_build_id=published.manifest.build_id,
        source_control=published.manifest.source_control,
        source_commit=published.manifest.source_commit,
        source_dirty=published.manifest.source_dirty,
        created_at=timestamp,
        updated_at=timestamp,
        repository_classification=classification,
        template=template,
    )


def _updated_metadata(
    current: Metadata,
    published: PublishedIndex,
    *,
    timestamp: str,
) -> Metadata:
    classification = current.repository_classification
    template = current.template
    if classification is not None and template is not None:
        classification = _classify_published(
            published, template_override=classification.template_override
        )
        template = compose_template(
            classification.effective_primary.id,
            classification.topology.id,
            tuple(item.id for item in classification.facets),
            current.output_language,
        ).identity
        if template != current.template:
            raise RepositoryError(
                "wiki_template_state_stale",
                "Repository classification now selects a different Wiki template; "
                "run wiki init.",
            )
    return replace(
        current,
        repository=str(published.repository),
        repository_fingerprint=published.manifest.repository_fingerprint,
        index_schema_version=INDEX_SCHEMA_VERSION,
        index_build_id=published.manifest.build_id,
        source_control=published.manifest.source_control,
        source_commit=published.manifest.source_commit,
        source_dirty=published.manifest.source_dirty,
        updated_at=timestamp,
        repository_classification=classification,
        template=template,
    )


def _evidence_query(page: Page) -> str:
    query = "\n".join(
        (
            page.title,
            page.description,
            *(f"path:{path}" for path in page.relevant_files),
            *(
                value
                for subsection in page.subsections
                for value in (
                    subsection.title,
                    subsection.description,
                    *(f"path:{path}" for path in subsection.direct_source_paths),
                )
            ),
        )
    )
    if len(query) > MAX_EVIDENCE_QUERY_LENGTH:
        raise RepositoryError(
            "wiki_evidence_query_too_large",
            "Wiki page retrieval query exceeds the supported size.",
            details={
                "max_characters": MAX_EVIDENCE_QUERY_LENGTH,
                "page_id": page.id,
            },
        )
    return query


def _direct_evidence_hits(
    page: Page,
    published: PublishedIndex,
    ranked_hits: tuple[SearchHit, ...],
) -> tuple[tuple[SearchHit, ...], dict[str, tuple[tuple[str, str], ...]]]:
    required = tuple(
        (subsection.id, path)
        for subsection in page.subsections
        if not subsection.documentation_only
        for path in subsection.direct_source_paths
    )
    ranked_by_path: dict[str, list[SearchHit]] = {}
    for hit in ranked_hits:
        ranked_by_path.setdefault(hit.chunk.path, []).append(hit)
    missing_paths = {path for _, path in required} - set(ranked_by_path)
    if missing_paths:
        query_terms = frozenset(tokenize_code(_evidence_query(page)))
        with IndexStore.open_readonly(published.database) as store:
            for chunk in store.get_chunks():
                if chunk.path in missing_paths:
                    chunk_terms = frozenset(tokenize_code(chunk.text))
                    lexical_score = float(len(query_terms & chunk_terms))
                    ranked_by_path.setdefault(chunk.path, []).append(
                        SearchHit(
                            chunk=chunk,
                            lexical_score=lexical_score,
                            structural_score=None,
                            vector_score=None,
                            fused_score=lexical_score,
                            reasons=("required_direct_path",),
                        )
                    )
    selected: list[SearchHit] = []
    coverage: dict[str, list[tuple[str, str]]] = {}
    for subsection_id, path in required:
        candidates = ranked_by_path.get(path, [])
        if not candidates:
            raise InvocationError(
                "wiki_direct_source_unavailable",
                "A declared direct source has no indexed Chunk.",
                details={"page_id": page.id, "path": path},
            )
        hit = min(
            candidates,
            key=lambda item: (
                item.chunk.symbol_id is None,
                -item.fused_score,
                item.chunk.start_line,
                item.chunk.end_line,
                item.chunk.id,
            ),
        )
        if hit.chunk.id not in coverage:
            selected.append(hit)
            coverage[hit.chunk.id] = []
        coverage[hit.chunk.id].append((subsection_id, path))
    return tuple(selected), {
        chunk_id: tuple(values) for chunk_id, values in coverage.items()
    }


def _find_page(wiki: Wiki, page_id: str) -> Page | None:
    return next(
        (
            page
            for section in wiki.sections
            for page in section.pages
            if page.id == page_id
        ),
        None,
    )


def _replace_page(wiki: Wiki, replacement: Page) -> Wiki:
    return replace(
        wiki,
        sections=tuple(
            replace(
                section,
                pages=tuple(
                    replacement if page.id == replacement.id else page
                    for page in section.pages
                ),
            )
            for section in wiki.sections
        ),
    )


def _reset_stale_pages(wiki: Wiki, stale_ids: frozenset[str]) -> Wiki:
    return replace(
        wiki,
        sections=tuple(
            replace(
                section,
                pages=tuple(
                    page.transition_to(PageStatus.PENDING)
                    if page.id in stale_ids
                    and page.status in {PageStatus.EVIDENCE_READY, PageStatus.GENERATED}
                    else page
                    for page in section.pages
                ),
            )
            for section in wiki.sections
        ),
    )


def _with_ready_evidence(
    page: Page,
    *,
    evidence: tuple[EvidenceRef, ...],
    snapshot: EvidenceSnapshot,
) -> Page:
    pending = (
        page
        if page.status is PageStatus.PENDING
        else page.transition_to(PageStatus.PENDING)
    )
    return replace(
        pending.transition_to(PageStatus.EVIDENCE_READY),
        evidence=evidence,
        evidence_snapshot=snapshot,
        citation_ids=(),
        error=None,
    )


def _with_generated_content(page: Page, submission: PageSubmission) -> Page:
    ready = page
    if page.status is PageStatus.FAILED:
        ready = page.transition_to(PageStatus.PENDING).transition_to(
            PageStatus.EVIDENCE_READY
        )
    return replace(
        ready.transition_to(PageStatus.GENERATED),
        body=None,
        subsection_contents=submission.subsections,
        citation_ids=tuple(
            dict.fromkeys(
                evidence_id
                for content in submission.subsections
                for evidence_id in content.evidence_ids
            )
        ),
        error=None,
    )


def _page_ids(wiki: Wiki) -> tuple[str, ...]:
    return tuple(page.id for section in wiki.sections for page in section.pages)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _require_fields(document: JsonObject, expected: set[str], label: str) -> None:
    if set(document) != expected:
        raise ValueError(f"{label} are invalid")


def _object(value: JsonValue) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("value must be an object")
    return value


def _array(value: JsonValue) -> list[JsonValue]:
    if not isinstance(value, list):
        raise TypeError("value must be an array")
    return value


def _string(value: JsonValue) -> str:
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    return value


def _string_tuple(value: JsonValue) -> tuple[str, ...]:
    items = _array(value)
    if not all(isinstance(item, str) for item in items):
        raise TypeError("value must contain only strings")
    return tuple(cast(list[str], items))


def _boolean(value: JsonValue) -> bool:
    if not isinstance(value, bool):
        raise TypeError("value must be a boolean")
    return value


def _string_items(document: JsonObject) -> tuple[tuple[str, str], ...]:
    if not all(isinstance(value, str) for value in document.values()):
        raise TypeError("framework labels must contain only strings")
    return tuple((key, cast(str, value)) for key, value in sorted(document.items()))


__all__ = [
    "METADATA_SCHEMA_VERSION",
    "STRUCTURE_SCHEMA_VERSION",
    "MAX_EVIDENCE_QUERY_LENGTH",
    "StructureUpdate",
    "WikiBuildUpdate",
    "WikiService",
    "WikiEvidenceUpdate",
    "WikiPageUpdate",
    "WikiState",
    "WikiStructure",
    "structure_from_document",
]
