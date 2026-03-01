# -*- mode: python ; coding: utf-8 -*-
# forge_host.spec — PyInstaller build spec (host standalone)
#
# Gera binário ultra-leve: dist/forge_host (~5MB)
# Uso: pyinstaller forge_host.spec

block_cipher = None

a = Analysis(
    ['src/adapters/cli/host_main.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'src.adapters.cli.host_main',
        'src.application.usecases.intercept_types',
        'src.application.usecases.terminal_session',
        'src.application.usecases.share_session',
        'src.application.usecases.output_renderer',
        'src.application.usecases.chat_manager',
        'src.infrastructure.config.loader',
        'src.infrastructure.collab.relay_bridge',
        'src.infrastructure.collab.host_relay_client',
        'src.infrastructure.collab.session_manager',
        'src.infrastructure.collab.machine_id',
        'src.infrastructure.collab.protocol',
        'src.infrastructure.terminal_engine.pty_engine',
        'src.infrastructure.terminal_engine.alternate_screen',
        'src.infrastructure.terminal_engine.split_renderer',
        'src.infrastructure.terminal_engine.input_router',
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
        'src.infrastructure.collab.relay_handler',
        'src.infrastructure.collab.viewer_client',
        'src.infrastructure.collab.agent_client',
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
    name='forge_host',
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
