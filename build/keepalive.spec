# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for keepalive.exe
#
# Run from the project root:
#   pyinstaller build/keepalive.spec
#
# Output: dist/keepalive.exe  (single-file, no console window)

import os

# SPECPATH is the directory containing this spec file (i.e. build/).
# Resolve the src/ and build/ directories relative to it.
src_dir   = os.path.abspath(os.path.join(SPECPATH, '..', 'src'))
build_dir = os.path.abspath(SPECPATH)
icon_path = os.path.join(build_dir, 'keepalive.ico')

a = Analysis(
    [os.path.join(src_dir, 'main.py')],
    pathex=[src_dir],
    binaries=[],
    # Bundle the icon so main.py can load it at runtime via sys._MEIPASS.
    datas=[(icon_path, '.')],
    hiddenimports=[
        # pywin32 components that PyInstaller sometimes misses
        'win32api',
        'win32con',
        'win32gui',
        'win32process',
        'pywintypes',
        # tkinter — stdlib but occasionally needs an explicit hint
        'tkinter',
        'tkinter.font',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    icon=icon_path,
    name='keepalive',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no black console window behind the GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
