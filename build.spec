# -*- mode: python ; coding: utf-8 -*-

my_root = os.getcwd()

a = Analysis(['src/autobuy/__main__.py'],
             pathex=['.venv/Lib/site-packages'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None,
             )
             
pyz = PYZ(a.pure)

options = [('u', None, 'OPTION'), ('u', None, 'OPTION'), ('u', None, 'OPTION')]

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          options,
          name='Bloodweb AutoBuy',
          debug=False,
          strip=None,
          upx=True,
          console=False,
          windowed=True,
          icon=os.path.join(my_root, 'data', 'program_icon.ico'))