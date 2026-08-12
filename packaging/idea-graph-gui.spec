from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

project_root = Path.cwd()
hidden_imports = collect_submodules("langgraph")

analysis = Analysis(
    [str(project_root / "src/desktop/__main__.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "config"), "config"),
        (str(project_root / "verified-urls.json"), "."),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "mypy", "ruff"],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="IdeaDiscoveryGraph",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="IdeaDiscoveryGraph",
)

app = BUNDLE(
    collection,
    name="Idea Discovery Graph.app",
    icon=None,
    bundle_identifier="dev.huntlab.idea-discovery-graph",
    info_plist={
        "CFBundleDisplayName": "Idea Discovery Graph",
        "CFBundleName": "Idea Discovery Graph",
        "NSHighResolutionCapable": True,
    },
)
