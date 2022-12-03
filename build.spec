# -*- mode: python ; coding: utf-8 -*-
import os
my_root = os.getcwd()

added_files = [
    ('data/2560x1440.csv','data'),
    ('data/resolutions.txt', 'data')
]

image_overrides = Tree('data/images', prefix='data/images')

a = Analysis(['src/autobuy/__main__.py'],
             pathex=['.venv/Lib/site-packages'],
             hiddenimports=[],
             hookspath=None,
             datas=added_files,
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
          image_overrides,
          name='Bloodweb AutoBuy',
          debug=False,
          strip=None,
          upx=True,
          console=False,
          windowed=True,
          icon=os.path.join(my_root, 'data/images', 'program_icon.ico'))
