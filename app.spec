# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

block_cipher = None

# The platform backend pywebview picks at runtime is imported by name, and on
# Windows it carries the WebView2 interop assemblies as package data, so
# nothing short of collecting the whole package brings a working window along.
webview_datas, webview_binaries, webview_hiddenimports = collect_all('webview')


a = Analysis(['app.py'],
             pathex=['./sensorview'],
             binaries=webview_binaries,
             datas=[('./assets', 'assets'), ('./assets/fonts/bootstrap-icons.woff', "assets/fonts"), ('./assets/fonts/bootstrap-icons.woff2', "assets/fonts"), ("./view_callbacks", "view_callbacks")] + webview_datas,
             # imageio_ffmpeg is imported lazily inside dataio.video.find_ffmpeg;
             # naming it here guarantees PyInstaller's hook runs and bundles the
             # static ffmpeg binary that transcodes non-mp4 recordings.
             hiddenimports=['numpy.core.multiarray', 'numpy.core.numeric', 'dash.backends._flask', 'dash.backends', 'imageio_ffmpeg', 'waitress'] + webview_hiddenimports,
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
