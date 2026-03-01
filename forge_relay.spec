# -*- mode: python ; coding: utf-8 -*-
# forge_relay.spec — PyInstaller build spec (relay standalone)
#
# Gera binário ultra-leve: dist/forge_relay (~5MB)
# Uso: pyinstaller forge_relay.spec

block_cipher = None

a = Analysis(
    ['src/adapters/cli/relay_main.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'src.adapters.cli.relay_main',
        'src.infrastructure.config.loader',
        'src.infrastructure.collab.relay_handler',
        'src.infrastructure.collab.protocol',
        'websockets',
        'yaml',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'forge_llm',
        'pyte',
        'httpx',
        'httpcore',
        'readability',
        'lxml',
        'src.infrastructure.intelligence',
        'src.infrastructure.agent',
        'src.application.usecases.nl_interceptor',
        'src.application.usecases.nl_mode_engine',
        'pytest',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='forge_relay',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
