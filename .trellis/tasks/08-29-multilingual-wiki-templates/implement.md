# Implementation

1. Test and implement contribution, node, slot, locale, and composed-contract models.
2. Test and implement deterministic merge/conflict/hash behavior.
3. Author all primary/topology/facet Markdown guidance in `en`, `zh-CN`, and `ja`.
4. Add parity, detail, placeholder, resource-enumeration, and composition tests.
5. Run `make check` and `make test-all`; complete the locale/template checkpoint.

Risky areas: the large locale matrix, composition cycles, duplicate logical IDs, and
guidance drift. Review all three catalogs and framework-shell ownership at checkpoint.
Rollback removes unreferenced resources before validator/state integration.
