# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ['src/app_v2.py'],
    pathex=['src'],
    binaries=[],
    datas=[('data/quests.json', 'data'), ('data/routes.json', 'data')],
    hiddenimports=['PIL.ImageGrab', 'PIL.ImageEnhance', 'PIL.ImageOps', 'winrtocr'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='OSRSQuestNavigator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
