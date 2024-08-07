# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['app.py'],
             pathex=['./sensorview'],
             binaries=[],
             datas=[('./assets', 'assets'), ('./assets/fonts/bootstrap-icons.woff', "assets/fonts"), ('./assets/fonts/bootstrap-icons.woff2', "assets/fonts"), ("./view_callbacks", "view_callbacks")],
             hiddenimports=['numpy.core.multiarray', 'numpy.core.numeric'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='sensorview',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          icon='assets/favicon.ico' )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='sensorview')
