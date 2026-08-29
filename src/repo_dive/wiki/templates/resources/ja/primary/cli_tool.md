<!-- repo-dive:contribution=cli_tool; locale=ja; -->
<!-- repo-dive:page=cli_installation_page; order=1; cardinality=1; shape=heading,paragraph,list,code_block; purpose=CLI の導入と起動を説明する; evidence=必須の根拠は package metadata、実行入口、導入命令、行番号; constraints=根拠ある前提と実行可能な命令だけを使う; -->
**{{repo_dive:cli_installation_page}}**：前提、導入方法、実行ファイル、初回呼出を記録する。
<!-- repo-dive:page=command_reference_page; order=2; cardinality=1; shape=heading,paragraph,table,code_block; purpose=正確なコマンドとオプションのリファレンスを提供する; evidence=必須の根拠は引数宣言、help 契約、handler、行番号; constraints=名前、既定値、必須性、予算、出力、例を正確に保つ; -->
**{{repo_dive:command_reference_page}}**：コマンド、引数、オプション、既定値、出力、呼出例を列挙する。
<!-- repo-dive:page=cli_configuration_page; order=3; cardinality=1; shape=heading,paragraph,table,code_block; purpose=CLI 設定の優先順位と検証を説明する; evidence=必須の根拠は設定 model、file、flag、行番号; constraints=根拠ある値と優先順位だけを記載する; -->
**{{repo_dive:cli_configuration_page}}**：設定源、優先順位、検証、既定値、安全な例を示す。
<!-- repo-dive:page=execution_flow_page; order=4; cardinality=1; shape=heading,paragraph,list,code_block; purpose=モジュール間の実行フローを追跡する; evidence=必須の根拠は入口、dispatch、service、adapter、行番号; constraints=決定的順序と stdout、stderr、副作用を区別する; -->
**{{repo_dive:execution_flow_page}}**：解析、検証、処理、adapter、出力、終了選択を追跡する。
<!-- repo-dive:page=cli_extension_points_page; order=5; cardinality=1; shape=heading,paragraph,table,code_block; purpose=対応する CLI 拡張境界を説明する; evidence=必須の根拠は protocol、registry、adapter、constructor、行番号; constraints=内部実装を対応 API として扱わない; -->
**{{repo_dive:cli_extension_points_page}}**：明示的 interface、登録、互換性制限を記録する。
<!-- repo-dive:page=errors_exit_codes_page; order=6; cardinality=1; shape=heading,paragraph,table,code_block; purpose=失敗、診断、終了コードを対応付ける; evidence=必須の根拠は exception、error envelope、exit constant、行番号; constraints=安定 code、channel、retry 指針を正確に保つ; -->
**{{repo_dive:errors_exit_codes_page}}**：検証、入力、運用、内部失敗の観測動作を列挙する。
