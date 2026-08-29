<!-- repo-dive:contribution=web_application; locale=ja; -->
<!-- repo-dive:page=web_runtime_architecture_page; order=1; cardinality=1; shape=heading,paragraph,list,code_block; purpose=ブラウザとサーバーの実行境界を説明する; evidence=必須の根拠は入口、構成要素、呼出経路、シンボル、1 始まり行番号; constraints=H4/H5、本文、一覧、コードを順序どおり使い外枠見出しを再現しない; -->
**{{repo_dive:web_runtime_architecture_page}}**：起動、描画、要求処理、状態所有、障害境界を追跡する。
<!-- repo-dive:page=routes_interfaces_page; order=2; cardinality=1; shape=heading,paragraph,table,code_block; purpose=ルートと外部インターフェースを記録する; evidence=必須の根拠は宣言、ハンドラー、スキーマ、シンボル、行番号; constraints=正確な名前、表、根拠ある例のみを使う; -->
**{{repo_dive:routes_interfaces_page}}**：入力、出力、認証、実装所有者を説明する。
<!-- repo-dive:page=web_state_persistence_page; order=3; cardinality=1; shape=heading,paragraph,table,list; purpose=クライアントとサーバーの状態永続化を説明する; evidence=必須の根拠はストア、モデル、移行、キャッシュ、行番号; constraints=一時状態と永続状態を分け、宣言順序を守る; -->
**{{repo_dive:web_state_persistence_page}}**：状態の生成者、利用者、整合性、無効化を対応付ける。
<!-- repo-dive:page=web_security_page; order=4; cardinality=1; shape=heading,paragraph,table,list; purpose=Web の信頼境界と制御を説明する; evidence=必須の根拠は認証、認可、検証、ヘッダー、行番号; constraints=根拠ある制御だけを記載する; -->
**{{repo_dive:web_security_page}}**：ID、セッション、認可、入力、ブラウザ保護、秘密を扱う。
<!-- repo-dive:page=web_deployment_operations_page; order=5; cardinality=1; shape=heading,paragraph,list,code_block; purpose=ビルド、配備、運用を説明する; evidence=必須の根拠はビルド、環境、配備マニフェスト、行番号; constraints=命令を根拠化しビルド時と実行時を分ける; -->
**{{repo_dive:web_deployment_operations_page}}**：成果物、環境、ロールアウト、監視、復旧を説明する。
<!-- repo-dive:page=web_testing_page; order=6; cardinality=1; shape=heading,paragraph,list,code_block; purpose=Web テスト戦略を説明する; evidence=必須の根拠はテスト、fixture、ブラウザ harness、命令、行番号; constraints=単体、統合、ブラウザ範囲を区別する; -->
**{{repo_dive:web_testing_page}}**：テスト層、準備、命令、範囲を示す。
