# csr_automation_toolkit.spec
# Build with: pyinstaller csr_automation_toolkit.spec
#
# Produces a single-file Windows .exe with no console window (GUI app),
# no Python install required on the teammate's machine.

block_cipher = None

a = Analysis(
    ['csr_automation_toolkit.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'gspread',
        'oauth2client.service_account',
        'google.auth',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='CSR_Automation_Toolkit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # No black console window — GUI only
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # Add icon='csr_icon.ico' here once you have one
)
