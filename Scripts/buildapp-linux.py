# Usage: python3 buildapp-linux.py [--debug] [--verbose] [--write-output] [--skip-app-creation]
    # --debug: adds extra debug options
    # --verbose: show stdout/stderr from pyinstaller
    # --keep-output: skip deleting BuildAppOutput.py
    # --skip-app-creation: skips running pyinstaller
    # --skip-script-generate: uses an already-made BuildAppOutput.py (and forces keep-output)

from pathlib import Path
import re
import sys
import platform
import subprocess
import os

dir = Path(__file__).resolve().parent.parent
file = dir / "ProperTree.py"
args = sys.argv[1:]
command = f'pyinstaller --add-data Scripts:Scripts {dir}/BuildAppOutput.py --name ProperTree --onefile -y'

if platform.system() != "Linux":
    print("Can only be run on Linux")
    exit()

if "--skip-app-creation" not in args:
    try:
        result = subprocess.run(['which', 'pyinstaller'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.stdout:
            print(f"Found pyinstaller: {result.stdout.decode().strip()}")
        else:
            print("pyinstaller not found: \"which pyinstaller\" could not find a valid command.\nPlease install pyinstaller as a globally accessible command.")
            exit()
    except Exception as e:
        print(f"pyinstaller not found: {e}\nPlease install pyinstaller as a globally accessible command.")
        exit()

with open(file, 'r') as f:
    code = f.read()

file_exists_check_pattern = r'os\.path\.exists\("Scripts/(.*?)"\)'
file_exists_check_match = re.search(file_exists_check_pattern, code)

open_file_pattern = r'open\("Scripts/(.*)"\)'
open_file_match = re.search(open_file_pattern, code)

if file_exists_check_match:
    print("Match: file_exists_check")
    value = file_exists_check_match.group(1)
    code = re.sub(file_exists_check_pattern, f'os.path.exists(os.path.join(sys._MEIPASS,"Scripts","{value}"))', code)
else:
    print("No match: file_exists_check")

if open_file_match:
    print("Match: open_file")
    value = open_file_match.group(1)
    code = re.sub(open_file_pattern, f'open(os.path.join(sys._MEIPASS,"Scripts","{value}"))', code)
else:
    print("No match: open_file")

code = code.replace('os.path.join(os.path.abspath(os.path.dirname(__file__)),"Scripts","update_check.py")', 'os.path.join(sys._MEIPASS,"Scripts","update_check.py")')
code = code.replace('os.path.dirname(__file__)', 'sys._MEIPASS')

#code = '\n'.join(code.split('\n')[:21] + ["# added debug line\nraise Exception(f\"tempdir: {sys._MEIPASS} ;; tempdir[ls]: {subprocess.run(['ls', f'{sys._MEIPASS}/Scripts'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)}\")"] + code.split('\n')[21:])

if "--debug" in args:
    code = '\n'.join([line for line in code.replace('mb.showerror(', 'debug_exception(').split('\n') if "tk.bell()" not in line])
    code = '\n'.join(code.split('\n')[:21] + [f"""\n# Generated Debug Exception Handler\ndef debug_exception(*args):
    raise Exception(
        f"--- DEBUG EXCEPTION CAUGHT ({{len(args)}} arguments) --\\n\\n" + 
        "\\n".join(str(arg) for arg in args)
    )\n"""] + code.split('\n')[21:])

if "--skip-script-generate" not in args:
    with open(dir / 'BuildAppOutput.py', 'w') as file:
        print("Writing output...")
        file.write(code)

if "--skip-app-creation" not in args:
    print("Creating application...")
    result = subprocess.run(command.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if "--verbose" in args:
        if (result.stdout):
            print(f"-- Verbose output (stdout) --\n{result.stdout.decode().strip()}")
        else:
            print(f"-- Verbose output (stderr) --\n{result.stderr.decode().strip()}")

    print(f"Created executable in ${Path(__file__).resolve().parent.parent}/dist")

if "--keep-output" not in args and "--skip-script-generate" not in args:
    print("Deleting temporary file...")
    os.remove(dir / 'BuildAppOutput.py')

print("Done!")