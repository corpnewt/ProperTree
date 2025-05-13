# Usage: python3 buildapp-linux.py [--verbose] [--python [@]]
    # "--verbose": Verbose mode.
    # "--python [@]": Select a Python executable to use (default is output of "which python3").

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
settings = Path(f'/home/{os.environ.get('USER')}/.ProperTree').resolve() # /home/$USER/.ProperTree
args = sys.argv[1:]
verbose = "--verbose" in args

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
tail -n+$S "$0" | tar xz -C "/tmp/.ProperTree"
{python} /tmp/.ProperTree/ProperTree.py "$@"
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

# Put a small notice on the code.
code = f"# This code has been processed and edited from the original ProperTree.py.\n\n{code}"

# Here, we're gonna transfer settings.json and version.json to our new settings directory.
if os.path.exists(scripts / "settings.json"):
    print("Copying settings.json...")
    shutil.copy(scripts / "settings.json", settings / "settings.json")
print("Copying version.json...")
shutil.copy(scripts / "version.json", settings / "version.json")

# This creates /dist, /dist/linux, /dist/linux/payload, and /dist/linux/payload/Scripts all in one check.
log(f"Creating output directories... (sources: [{payload_scripts}])")
if not os.path.exists(payload_scripts):
    os.makedirs(payload_scripts)

print("Writing main.sh...")
with open(dist / 'main.sh', 'w') as file:
    file.write(script)

with open(payload_dir / 'ProperTree.py', 'w') as file:
    file.write(code)

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

# Done!
print("Done!")
exit(0)