# Design

Keep commands as thin adapters over completed classifier/template/validator/Wiki
services. Validation nonconformance uses `InvocationError` and the existing exit-`2`
error envelope with bounded details, preserving global process semantics. `wiki
validate --input` means one complete document governed by persisted Schema `2.0`;
page-fragment validation remains in `wiki page`. JSON is the canonical agent contract.
Documentation and executable help are updated together, while package smoke proves
runtime resource inclusion. Rollback can remove additive commands while leaving the
last valid `wiki.md`; it must not attempt to downgrade Schema `2.0` state.
