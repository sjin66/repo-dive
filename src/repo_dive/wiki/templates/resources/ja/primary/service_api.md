<!-- repo-dive:contribution=service_api; locale=ja; -->
<!-- repo-dive:page=service_runtime_architecture_page; order=1; cardinality=1; shape=heading,paragraph,list,code_block; purpose=サービス起動と要求処理を説明する; evidence=必須の根拠は入口、middleware、handler、依存、行番号; constraints=処理順を保ち外枠見出しを再現しない; -->
**{{repo_dive:service_runtime_architecture_page}}**：初期化、分配、ドメイン処理、永続化、応答を追跡する。
<!-- repo-dive:page=api_contracts_page; order=2; cardinality=1; shape=heading,paragraph,table,code_block; purpose=安定 API 契約を記録する; evidence=必須の根拠は仕様、スキーマ、endpoint、行番号; constraints=method、field、status を正確に保つ; -->
**{{repo_dive:api_contracts_page}}**：要求、応答、互換性、所有者を説明する。
<!-- repo-dive:page=request_validation_page; order=3; cardinality=1; shape=heading,paragraph,table,code_block; purpose=要求検証とエラー対応を説明する; evidence=必須の根拠は validator、parser、error type、行番号; constraints=呼出検証とドメイン失敗を分ける; -->
**{{repo_dive:request_validation_page}}**：未信頼入力、正規化、拒否、安定エラーを追跡する。
<!-- repo-dive:page=service_persistence_page; order=4; cardinality=1; shape=heading,paragraph,table,list; purpose=データ所有と整合性を説明する; evidence=必須の根拠は model、query、transaction、migration、行番号; constraints=transaction 境界を明記し schema を推測しない; -->
**{{repo_dive:service_persistence_page}}**：データ、アクセス、整合性、移行、復旧を説明する。
<!-- repo-dive:page=service_security_page; order=5; cardinality=1; shape=heading,paragraph,table,list; purpose=サービス信頼境界を説明する; evidence=必須の根拠は認証、認可、秘密処理、行番号; constraints=設定方針とコード強制を区別する; -->
**{{repo_dive:service_security_page}}**：ID、認可、転送、入力安全、秘密を扱う。
<!-- repo-dive:page=service_operations_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=配備とサービス運用を説明する; evidence=必須の根拠は manifest、health check、telemetry、runbook、行番号; constraints=命令、失敗、rollback を根拠化する; -->
**{{repo_dive:service_operations_page}}**：配備、健全性、拡縮、障害、復旧を説明する。
