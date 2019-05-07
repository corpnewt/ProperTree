from setuptools import setup
import os, sys

ProperTree_PATH = os.path.dirname(os.path.realpath(__file__))
SCRIPTS_PATH = ProperTree_PATH + "/Scripts"
FILES = os.listdir(ProperTree_PATH)
PT_FILE = "ProperTree.py"

if not PT_FILE in FILES:
    if "ProperTree.command" in FILES:
        with open("ProperTree.command", 'r') as f:
            pt = f.readlines()
            pt.pop(0)
            pt = "".join(pt)
            with open(PT_FILE, 'w') as p:
                p.write(pt)
                p.close()

            f.close()

APP = [PT_FILE]
DATA_FILES = ["Scripts/{}".format(x) for x in os.listdir(SCRIPTS_PATH)]
OPTIONS = {'argv_emulation': True}

if sys.platform == 'darwin':
    setup(
        app=APP,
        data_files=DATA_FILES,
        options={'py2app': OPTIONS},
        setup_requires=['py2app'],
    )
elif sys.platform == 'win32':
    setup(
        app=APP,
        data_files=DATA_FILES,
        options={'py2exe': OPTIONS},
        setup_requires=['py2exe'],
    )

print("\n\nApp can be found in {}/dist/ProperTree".format(ProperTree_PATH))