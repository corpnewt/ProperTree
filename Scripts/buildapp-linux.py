# Usage: python3 buildapp-linux.py [--verbose] [--python [@]] [--always-overwrite] [--use-existing-payload]
    # "--verbose": Verbose mode.
    # "--python [@]": Select a Python executable to use (default is output of "which python3").
    # "--always-overwrite": Always overwrite applicable files instead of prompting.
    # "--use-existing-payload": Don't overwrite /dist/linux/payload/ProperTree.py.

# Generated Files - The script will build results in /dist/linux.
    # payload: This is where scripts and assets are processed and copied. This is what is extracted when the app is ran. It will extract into /tmp/.ProperTree/app.
    # shell: This is the directory used for makefile compilation.
    # result: This is the directory with the results. It will have a ProperTree.sh (the raw shell file) and (maybe) an ELF executable named ProperTree.

from pathlib import Path
import sys
import platform
import subprocess
import os
import shutil
import tarfile

dir = Path(__file__).resolve().parent.parent
scripts = dir / "Scripts"
dist = dir / "dist" / "linux"
payload_dir = dist / "payload"
payload_scripts = payload_dir / "Scripts"
result_dir = dist / "result"
settings = Path(f'/home/{os.environ.get('USER')}/.ProperTree').resolve() # /home/$USER/.ProperTree
args = sys.argv[1:]
verbose = "--verbose" in args

# Delete /dist if it exists
if os.path.exists(dist):
    if "--use-existing-payload" in args:
        if os.path.exists(dist / "archive"):
            shutil.rmtree(dist / "archive")
        if os.path.exists(dist / "result"):
            shutil.rmtree(dist / "result")
        for item in os.listdir(dist):
            item_path = os.path.join(dist, item)
            if os.path.isfile(item_path):
                os.remove(item_path)
    else:
        # Destroy it all
        shutil.rmtree(dist)

# For verbose-specific logs.
def log(*args):
    if verbose:
        print('\n'.join(map(str, args)))

def is_python(path):
    if not os.path.isfile(path) or not os.access(path, os.X_OK):
        log(f"is_python fail: not os.path.isfile({path}) or not os.access({path}, os.X_OK)")
        return False
    
    try:
        result = subprocess.run([path, '-V'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        log(f"is_python log: result: {result}")

        if result.returncode == 0:
            log(f"is_python success: {result.returncode}")
            return True
    except Exception as e:
        log(f"is_python fail: exception:\n{e}")
        return False
    
    log("is_python fail: overlow[1]")
    return False

if platform.system() != "Linux":
    print("Can only be run on Linux")
    exit(1)

if "--python" in args:
    if args.index("--python") + 1 < len(args):
        python = args[args.index("--python") + 1]
        if not is_python(python):
            print(f"Invalid python executable: {python}")
            exit(1)
    else:
        print("Invalid Python executable: no executable provided")
        exit(1)
else:
    result = subprocess.run(["which", "python3"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.stdout:
        python = result.stdout.decode().strip()
    else:
        print("Invalid Python executable: no executable found")
        exit(1)

# Success
print(f"Found Python: {python}")

# Generate the extraction script. It's meant to be as compact as possible.
script = f"""#!/bin/bash
S=$(awk '/^A/ {{print NR + 1; exit 0; }}' "$0")
mkdir "/tmp/.ProperTree" > /dev/null
mkdir "/tmp/.ProperTree/app" > /dev/null
tail -n+$S "$0" | tar xz -C "/tmp/.ProperTree/app"
{python} /tmp/.ProperTree/app/ProperTree.py "$@"
rm -rf "/tmp/.ProperTree"
exit 0
A
"""

# We're gonna put our settings into a persistent user-specific directory, since otherwise it'd go into a temporary directory, which we don't want.
if not os.path.exists(settings):
    os.makedirs(settings)

print("Processing code...")
# Load ProperTree.py's code so we can edit it.
with open(dir / "ProperTree.py", 'r') as file:
    code = file.read()

# These next lines make sure ProperTree uses our new settings directory.
code = code.replace('Scripts/settings.json', f"{settings}/settings.json")
code = code.replace('Scripts/version.json', f"{settings}/version.json")
code = code.replace('join(pt_path,"Configuration.tex")', f'join("{settings}", "Configuration.tex")')

def copy_settings_json():
    print("Copying settings.json...")
    shutil.copy(scripts / "settings.json", settings / "settings.json")

# Here, we're gonna transfer settings.json and version.json to our new settings directory.
if os.path.exists(scripts / "settings.json"):
    # If the file already exists, then ask the user if they want to overwrite it.
    if os.path.exists(settings / "settings.json") and "--always-overwrite" not in args:
        while True:
            response = input(f"Do you want to overwrite {settings / "settings.json"}? (y/n/x): >> ").strip().lower()
            if response == 'y':
                copy_settings_json()
                break
            elif response == 'n':
                break
            elif response == 'x': # Quit
                print("Done!")
                exit(0)
            else:
                print("Invalid input. Please enter 'y' or 'n'.")
    else:
        copy_settings_json()
print("Copying version.json...")
shutil.copy(scripts / "version.json", settings / "version.json")

# This creates /dist, /dist/linux, /dist/linux/payload, /dist/linux/payload/Scripts, /dist/linux/result all in one check.
log(f"Creating output directories... (sources: [{payload_scripts}, {result_dir}])")
if not os.path.exists(payload_scripts):
    os.makedirs(payload_scripts)
if not os.path.exists(result_dir):
    os.makedirs(result_dir)
if not os.path.exists(dist / "archive"):
    os.makedirs(dist / "archive")

if not os.path.exists(payload_dir / 'ProperTree.py') and "--use-existing-payload" in args:
    print("No ProperTree.py given for payload.")
    exit(1)

if "--use-existing-payload" not in args:
    with open(payload_dir / 'ProperTree.py', 'w') as file:
        file.write(code)

print("Writing main.sh...")
with open(dist / 'main.sh', 'w') as file:
    file.write(script)

# Copies from the Scripts folder into the payload's Scripts folders.
def copy_script(target):
    log(f"Copying Python script: {target}")
    shutil.copy(scripts / target, payload_scripts / target)

print("Copying scripts...")
copy_script("__init__.py")
copy_script("config_tex_info.py")
copy_script("downloader.py")
copy_script("plist.py")
copy_script("plistwindow.py")
copy_script("update_check.py")
copy_script("utils.py")

print("Creating payload...")
with tarfile.open(dist / "payload.tar.gz", "w:gz") as tar:
    for dirpath, dirnames, filenames in os.walk(payload_dir):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            tar.add(filepath, arcname=os.path.relpath(filepath, payload_dir))

# Here's where we add the payload.
result = subprocess.run(f"cat {dist}/payload.tar.gz >> {dist}/main.sh", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

print("Copying script...")
subprocess.run(["chmod", "+x", f"{dist}/main.sh"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
shutil.copy(dist / "main.sh", result_dir / "ProperTree.sh")

print("Generating ELF...")
result = subprocess.run(["makeself", "--quiet", "--tar-quietly", f'{dist / "archive"}', f"{dist / "main.run"}", "ProperTree", f"{dist / "main.sh"}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# If it exists, copy it. If it doesn't, just tell the user that it couldn't make an executable.
if os.path.exists(dist / "main.run"):
    log("Copying ELF executable...")
    shutil.copy(dist / "main.run", result_dir / "ProperTree")
else:
    print("WARNING: An ELF executable was not created. Please note that in order to create an ELF executable, makeself must be installed. (For more info, run with --verbose)")
    log(f"makeself stdio:\n{result.stdout}\n{result.stderr}")

# Done!
print("Done!")
exit(0)