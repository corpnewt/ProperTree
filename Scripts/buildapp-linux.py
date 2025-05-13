# Usage: python3 buildapp-linux.py [--verbose] [--python [@]] [--always-overwrite] [--use-existing-payload]
    # "--verbose": Verbose mode.
    # "--python [@]": Select a Python executable to use (default is output of "which python3").
    # "--always-overwrite": Always overwrite applicable files instead of prompting.
    # "--use-existing-payload": Don't overwrite /dist/linux/payload/ProperTree.py.
    # "--skip-compile": Skip compiling the script to an ELF executable.

# Generated Directories - The script will build in /dist/linux.
    # payload: This is where scripts and assets are processed and copied. This is what is extracted when the app is ran. It will extract into /tmp/.ProperTree/app-$ID.
    # result: This is the directory with the results. It will have a ProperTree.sh (the raw shell file) and (maybe) an ELF executable named ProperTree.

# Results - The script will build results in /dist/linux/result.
    # ProperTree.sh: The shell script containing ProperTree.
    # ProperTree: The optional ELF executable that can be run as an application instead of as a script.

from pathlib import Path
import re
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

# Delete /dist if it exists.
print(f"Clearing {dist}...")
if os.path.exists(dist):
    if "--use-existing-payload" in args:
        for item in os.listdir(dist):
            file = os.path.join(dist, item)
            if os.path.isdir(file):
                if item != "payload":
                    shutil.rmtree(file)
            else:
                os.remove(file)
    else:
        # Destroy it all
        shutil.rmtree(dist)

# Create /dist/linux.
if not os.path.exists(dist):
    os.makedirs(dist)

# Only clear /dist/linux.
if "--clear" in args:
    print("Done!")
    exit(0)

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

# Generate the extraction script. The script extracts the payload to "/tmp/.ProperTree/app-ID". "ID" is a random number between 0 and 32767.
# The script works by first ensuring directories exist, then copying settings.json and Configuration.tex (if they exist) to the new temporary directory. After ProperTree runs, then settings.json and Configuration.tex are placed back in /home/$USER/.ProperTree.
script = f"""#!/bin/bash
# This is an auto-generated script.
ID=$RANDOM
S=$(awk '/^A/ {{print NR + 1; exit 0; }}' "$0")
mkdir "/home/$USER/.ProperTree" > /dev/null 2>&1
mkdir "/tmp/.ProperTree" > /dev/null 2>&1
mkdir "/tmp/.ProperTree/app-$ID" > /dev/null 2>&1
tail -n+$S "$0" | tar xz -C "/tmp/.ProperTree/app-$ID"
cp "/home/$USER/.ProperTree/settings.json" "/tmp/.ProperTree/app-$ID/Scripts/settings.json" > /dev/null 2>&1
cp "/home/$USER/.ProperTree/Configuration.tex" "/tmp/.ProperTree/app-$ID/Configuration.tex" > /dev/null 2>&1
"{python}" "/tmp/.ProperTree/app-$ID/ProperTree.py" "$@"
cp "/tmp/.ProperTree/app-$ID/Scripts/settings.json" "/home/$USER/.ProperTree/settings.json" > /dev/null 2>&1
cp "/tmp/.ProperTree/app-$ID/Configuration.tex" "/home/$USER/.ProperTree/Configuration.tex" > /dev/null 2>&1
rm -rf "/tmp/.ProperTree" > /dev/null 2>&1
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
# Load linux-app.c's code so we can edit it.
with open(scripts / "linux-app.c", 'r') as file:
    ccode = file.read()

# These next lines make sure ProperTree uses our new settings directory.
#code = re.sub(r'join\(pt_path,["\']Configuration\.tex["\']\)', 'join(f"/home/{os.environ.get(\'USER\')}/.ProperTree", "Configuration.tex")', code)
#code = re.sub(r'["\']Scripts/settings.json["\']', "f'/home/{os.environ.get('USER')}/.ProperTree/settings.json'", code)

def copy_settings_json():
    print("Copying settings.json...")
    shutil.copy(scripts / "settings.json", settings / "settings.json")

# Here, we're gonna transfer settings.json to our new settings directory.
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
def copy_asset(target):
    log(f"Copying asset: {target}")
    shutil.copy(scripts / target, payload_scripts / target)

if "--use-existing-payload" not in args:
    print("Copying assets...")
    copy_asset("__init__.py")
    copy_asset("config_tex_info.py")
    copy_asset("downloader.py")
    copy_asset("plist.py")
    copy_asset("plistwindow.py")
    copy_asset("update_check.py")
    copy_asset("utils.py")
    copy_asset("menu.plist")
    copy_asset("snapshot.plist")
    copy_asset("version.json")

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

if "--skip-compile" not in args:
    print("Embedding script...")
    with open(dist / 'main.sh', 'rb') as file:
        binary = file.read()
        bytes = [f"0x{byte:02X}" for byte in binary]
    
    with open(dist / 'main.c', 'w') as file:
        file.write(ccode.replace('const unsigned char shell_script[] = {};', f'const unsigned char shell_script[] = {{\n    {', '.join(bytes)}\n}};'))

    print("Generating executable...")
    try:
        result = subprocess.run(["gcc", "-o", "dist/linux/main", f"{dist / "main.c"}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stderr = result.stderr
    except Exception as e:
        stderr = e

    # If it exists, copy it. If it doesn't, just tell the user that it couldn't make an executable.
    if os.path.exists(dist / "main"):
        log("Copying executable...")
        shutil.copy(dist / "main", result_dir / "ProperTree")
    else:
        print("WARNING: An ELF executable was not created. Please note that in order to create an ELF executable, gcc must be installed. (For more info, run with --verbose)")
        log(f"gcc error:\n{stderr}")

# Done!
print(f"Done! Results are in: {result_dir}")
exit(0)