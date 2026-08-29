# Deterministic repository classification

## Goal

Produce an auditable, repeatable primary/topology/facet classification from the
current validated repository index for template selection.

## Requirements

- Implement the taxonomy and deterministic fallback defined by the parent PRD.
- Evaluate only bounded path, language, and named-manifest signals from the published
  index; never disclose matched source content.
- Emit classifier/taxonomy versions, index identity, selection source, integer scores,
  ordered matched signals, detected and effective primary, topology, facets, and
  optional override.
- Support registered primary-template override without hiding detected overlays.

## Acceptance Criteria

- [x] Fixtures cover every primary archetype, topology, and facet.
- [x] Weak, absent, tied, malformed, and ambiguous evidence selects stable outcomes.
- [x] Repeated classification is byte-stable and independent of filesystem ordering.
- [x] Unknown overrides raise a typed domain validation error ready for the later CLI
  adapter; repository/index failures remain typed repository errors.

## Out of Scope

- Template composition, Markdown validation, and prose generation.

## Dependencies

- None. This is the first implementation child.
