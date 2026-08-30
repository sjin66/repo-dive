# PyInstaller onedir definition. Build only in the native target environment.
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = collect_data_files("repo_dive") + [("skills/wiki", "repo_dive/_skills/wiki")]
binaries = (
    collect_dynamic_libs("tree_sitter")
    + collect_dynamic_libs("tree_sitter_javascript")
    + collect_dynamic_libs("tree_sitter_typescript")
)

analysis = Analysis(
    ["scripts/frozen_entry.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "tree_sitter",
        "tree_sitter_javascript",
        "tree_sitter_typescript",
    ],
    excludes=["sentence_transformers", "torch", "transformers"],
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="repo-dive",
    console=True,
)
coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="repo-dive",
)
