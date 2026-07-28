# csr_automation_toolkit.spec
# Build with: pyinstaller csr_automation_toolkit.spec
#
# Produces a single-file Windows .exe with no console window (GUI app),
# no Python install required on the teammate's machine.
#
# NOTE ON hiddenimports:
# - 'openai' is imported lazily inside a function, so PyInstaller's bytecode
#   scan will not find it. It has to be declared explicitly.
# - 'gspread' and 'google.oauth2' back the optional Sheets logging.
#   gspread.service_account_from_dict pulls google.oauth2.service_account at
#   runtime; declare it so the optional feature survives packaging.
# - The build machine must have openai and gspread installed, or the .exe
#   ships permanently missing those optional features.
# - oauth2client is NOT a dependency. Auth goes through gspread's native
#   service-account support.
#
# NOTE ON console=False:
# There is no console in the packaged build, so nothing printed to stdout is
# ever visible. All diagnostics go to csr_errors.log in the user's config
# folder (%APPDATA%\CSRToolkit\csr_errors.log) and are surfaced in the app's
# status bar.
#
# NOTE ON upx=False:
# UPX-compressed unsigned executables are a classic antivirus false-positive
# trigger; the size saving isn't worth extra SmartScreen/AV friction during
# an internal pilot.
#
# NOTE ON responses.json:
# Listed in datas as a safety net, but the app's seeding code reads
# responses.json from NEXT TO the .exe, not from the PyInstaller bundle.
# Distribute the .exe and responses.json together as a pair (see PACKAGING.md).

block_cipher = None

a = Analysis(
    ['csr_automation_toolkit.py'],
    pathex=[],
    binaries=[],
    datas=[('responses.json', '.')],
    hiddenimports=[
        'gspread',
        'google.oauth2',
        'google.oauth2.service_account',
        'openai',
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
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # No black console window - GUI only
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # Add icon='csr_icon.ico' here once you have one
)
