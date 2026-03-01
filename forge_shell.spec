# -*- mode: python ; coding: utf-8 -*-
# forge_shell.spec — PyInstaller build spec
#
# Gera binário standalone Linux: dist/forge_shell
# Uso: pyinstaller forge_shell.spec
# Requer: pip install pyinstaller>=6.0 && pip install -e .

block_cipher = None

a = Analysis(
    ['src/adapters/cli/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'src.adapters.cli.main',
        'src.application.usecases.terminal_session',
        'src.application.usecases.intercept_types',
        'src.application.usecases.nl_interceptor',
        'src.application.usecases.nl_mode_engine',
        'src.application.usecases.doctor_runner',
        'src.application.usecases.share_session',
        'src.infrastructure.config.loader',
        'src.infrastructure.audit.audit_logger',
        'src.infrastructure.collab.relay_handler',
        'src.infrastructure.collab.relay_bridge',
        'src.infrastructure.collab.host_relay_client',
        'src.infrastructure.collab.viewer_client',
        'src.infrastructure.collab.session_manager',
        'src.infrastructure.collab.protocol',
        'src.infrastructure.intelligence.forge_llm_adapter',
        'src.infrastructure.intelligence.risk_engine',
        'src.infrastructure.intelligence.redaction',
        'websockets',
        'forge_llm',
        'yaml',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'unittest'],
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
    name='forge_shell',
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
