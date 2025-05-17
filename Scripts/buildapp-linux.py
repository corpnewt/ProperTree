# A Python script to compile ProperTree to run as a native Linux app. Officially supports x64 Debian-based distros, but any architecture/distro is theoretically supported.
    # ProperTree by: CorpNewt
    # This script by: Calebh101

# Notes:
    # This script places data in /home/$USER/.ProperTree. Please do not delete this directory or any files in it.
    # This script needs Python 3 to run.

# Usage: python3 buildapp-linux.py [--verbose] [--python [@]] [--always-overwrite] [--use-existing-payload]
    # "--verbose": Verbose mode.
    # "--python [@]": Select a Python executable to use (default is output of "which python3").
    # "--always-overwrite": Always overwrite applicable files instead of prompting.
    # "--use-existing-payload": Don't overwrite /dist/linux/payload/ProperTree.py. This was helpful in early debugging, where I was messing around with different techniques before deciding upon this one.
    # "--skip-compile": Skip compiling the script to an ELF executable.

# Generated Directories - The script will build in /dist/linux.
    # payload: This is where scripts and assets are processed and copied. This is what is extracted when the app is ran. It will extract into /tmp/.ProperTree/app-$ID.
    # result: This is the directory with the results. It will have a ProperTree.sh (the raw shell file) and (maybe) an ELF executable named ProperTree.

# Results - The script will build results in /dist/linux/result.
    # ProperTree.sh: The shell script containing ProperTree. This manages all of ProperTree's files and data.
    # ProperTree: The optional ELF executable that can be run as an application instead of as a script. This is only built for x64 systems, but for ARM-based systems, you can build main.c from source. main.c contains all the required data.
    # ProperTree-Installer-V.sh: Installs ProperTree as an application.

# The Scripts
    # ProperTree.sh: Runs ProperTree. Please note that it can be run with "--clear-data" to clear ProperTree data.
    # ProperTree-Installer-V.sh: Installs ProperTree by adding "ProperTree" and "propertree" to /home/$USER/.local/bin and adding ProperTree.desktop to /home/$USER/.local/share/applications. Please note that it can be run with "--uninstall" to delete these three files.

# The Process
    # 1. Generate a main script and an install script.
    # 2. Generate a payload by copying over required assets in /Scripts and compress it.
    # 3. Attach the payload to the main script.
    # 4. Attach the main script as another payload to the installer.
    # 5. Optionally compile a generated C file to the executable. This uses the least external resources possible, as it only used the base install of gcc. It does not need any extra tools or packages.
    # 6. Copy it all into result.

# Extra Files (in /dist/linux)
    # main: The exact same file as ProperTree (in /result).
    # main.sh: The exact same file as ProperTree.sh (in /result).
    # main.c: The generated source code for the executable. This can be used to compile the executable for multiple architectures. It contains all the necessary data, so you don't have to include multiple files.
    # payload.tar.gz: The compressed version of /payload.

# Known Issues
    # ARM is not officially supported by this script, but you can compile main.c (in /dist/linux) from source.
    # ProperTree does not have an icon in the taskbar. This is due to the fact that when you run the .desktop file from the launcher, it doesn't directly load a GUI; it goes through ProperTree.py, which loads a window by itself - separate from the launcher or the .desktop.
    # ProperTree's taskbar window is named "Toplevel". This is on ProperTree.py's side (most likely tkinter's side), and I do not know a fix for this at the moment.

from pathlib import Path
import sys
import platform
import subprocess
import os
import shutil
import tarfile
import json

dir = Path(__file__).resolve().parent.parent # Directory of ProperTree. All of the refrences of the other directories are based on this, aside from data and temporary directories.
scripts = dir / "Scripts" # /Scripts
dist = dir / "dist" / "linux" # /dist/linux
payload_dir = dist / "payload" # /dist/linux/payload
payload_scripts = payload_dir / "Scripts" # /dist/linux/payload/Scripts
result_dir = dist / "result" # /dist/linux/result
settings = Path(f'/home/{os.environ.get('USER')}/.ProperTree').resolve() # /home/user/.ProperTree

# Capture the arguments passed.
args = sys.argv[1:]

if platform.system() != "Linux":
    print("Can only be run on Linux")
    exit(1)

# For verbose-specific logs. These will only be seen with --verbose.
def log(*args):
    if "--verbose" in args:
        print('\n'.join(map(str, args)))

# Get the version of ProperTree.
with open(scripts / 'version.json', 'r') as file:
    version = json.load(file)['version']
    log(f'ProperTree version: {version}')

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

# Only clear /dist/linux if --clear is used.
if "--clear" in args:
    print("Done!")
    exit(0)

# Tries to see if the inputted Python executable is a valid one.
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

if "--python" in args:
    # Find the argument that they're claiming is a valid Python executable.
    if args.index("--python") + 1 < len(args):
        python = args[args.index("--python") + 1]
        if not is_python(python):
            print(f"Invalid python executable: {python}")
            exit(1)
    else: # Otherwise, they trolled us.
        print("Invalid Python executable: no executable provided")
        exit(1)
else: # If they didn't supply a Python, we take the result from "which python3". The reason we use "which python3" instead of "which python" is because there's typically not a default "python" executable, but Debian expects the user to use "python3".
    result = subprocess.run(["which", "python3"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.stdout:
        python = result.stdout.decode().strip()
        if not is_python(python):
            print(f"Invalid python executable: {python} (auto-detected)")
            exit(1)
    else:
        print("Invalid Python executable: no executable found")
        exit(1)

# Success
print(f"Found Python: {python}")

# Get the icon binary so we can embed it.
print("Processing icon...")
with open(scripts / "icon.png", 'rb') as f:
    content = f.read()
    icon = ''.join(f'\\x{byte:02X}' for byte in content)

# Generate the extraction script. The script extracts the payload to "/tmp/.ProperTree/app-ID". "ID" is a random number between 0 and 32767.
# The script works by first ensuring directories exist, then copying settings.json and Configuration.tex (if they exist) to the new temporary directory. After ProperTree runs, then settings.json and Configuration.tex are copied back in /home/user/.ProperTree and the temporary directory is deleted.
script = f"""#!/bin/bash
# This is an auto-generated script.
# ProperTree V. {version}
# Run with --clear-data to remove data.

for arg in "$@"; do
  if [ "$arg" == "--clear-data" ]; then
    echo "Removing data..."
    rm -rf "$HOME/.ProperTree/settings.json" > /dev/null 2>&1
    rm -rf "$HOME/.ProperTree/Configuration.tex" > /dev/null 2>&1
    echo "Done! ProperTree data has been cleared."
    exit 0
  fi
done

ID=$RANDOM
DATA=$(awk '/^BREAKER/ {{print NR + 1; exit 0; }}' "$0")
mkdir "$HOME/.ProperTree" > /dev/null 2>&1
mkdir "/tmp/.ProperTree" > /dev/null 2>&1
mkdir "/tmp/.ProperTree/app-$ID" > /dev/null 2>&1
tail -n+$DATA "$0" | tar xz -C "/tmp/.ProperTree/app-$ID"
cp "$HOME/.ProperTree/settings.json" "/tmp/.ProperTree/app-$ID/Scripts/settings.json" > /dev/null 2>&1
cp "$HOME/.ProperTree/Configuration.tex" "/tmp/.ProperTree/app-$ID/Configuration.tex" > /dev/null 2>&1
"{python}" "/tmp/.ProperTree/app-$ID/ProperTree.py" "$@"
cp "/tmp/.ProperTree/app-$ID/Scripts/settings.json" "$HOME/.ProperTree/settings.json" > /dev/null 2>&1
cp "/tmp/.ProperTree/app-$ID/Configuration.tex" "$HOME/.ProperTree/Configuration.tex" > /dev/null 2>&1
rm -rf "/tmp/.ProperTree/app-$ID" > /dev/null 2>&1
exit 0
BREAKER
"""

# Generate the install script. Also includes an uninstall option.
# We embed the icon binary so we can copy it over without relying on external files.
# BREAKER is now DESTROYER to avoid awk confusion.
# It also handles instances where /home/$USER/.local/bin isn't in path (or when it doesn't even exist), which happens on clean installations of Debian-based distros.
install_script = f"""#!/bin/bash
# This is an auto-generated script.
echo "Preparing..."

rm "$HOME/.local/bin/ProperTree" > /dev/null 2>&1
rm "$HOME/.local/bin/propertree" > /dev/null 2>&1
rm "$HOME/.local/share/applications/ProperTree.desktop" > /dev/null 2>&1

for arg in "$@"; do
  if [ "$arg" == "--uninstall" ]; then
    echo "Uninstalling..."
    rm "$HOME/.ProperTree/icon.png" > /dev/null 2>&1
    echo "Done! ProperTree uninstalled. Your data was not affected."
    exit 0
  fi
done

desktop="[Desktop Entry]
Name=ProperTree
Comment=By CorpNewt
Exec=$HOME/.local/bin/ProperTree
Icon=$HOME/.ProperTree/icon.png
Terminal=false
Type=Application
Categories=Utility
MimeType=text/xml;"

mkdir "$HOME/.ProperTree" > /dev/null 2>&1
mkdir "$HOME/.local" > /dev/null 2>&1
mkdir "$HOME/.local/bin" > /dev/null 2>&1
printf '{icon}' > "$HOME/.ProperTree/icon.png"

echo "Extracting payload..."
DATA=$(awk '/^DESTROYER/ {{print NR + 1; exit 0; }}' "$0")
tail -n+$DATA "$0" > "$HOME/.local/bin/ProperTree"

echo "Writing files..."
echo "$desktop" > "$HOME/.local/share/applications/ProperTree.desktop"

cat << 'EOF' > "$HOME/.local/bin/propertree"
#!/bin/bash
# This is an auto-generated script.
"$HOME/.local/bin/ProperTree" "$@"
EOF

echo "Managing permissions..."
chmod +x "$HOME/.local/bin/ProperTree"
chmod +x "$HOME/.local/bin/propertree"

echo "Refreshing sources..."
update-desktop-database ~/.local/share/applications
source ~/.bashrc

if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "WARNING: $HOME/.local/bin is not in PATH. You will not be able to run ProperTree from the command line if it's not in PATH."
    echo 'Please add `PATH="$PATH:$HOME/.local/bin"` to PATH in .bashrc or whatever you use.'
fi

echo "Done! Run this script with --uninstall to uninstall the ProperTree application. You can also run ProperTree with --clear-data to clear ProperTree data."
exit 0
DESTROYER
"""

# We're gonna put our settings into a persistent user-specific directory, since otherwise ProperTree would generate it in a temporary directory, which we don't want as it just gets deleted.
if not os.path.exists(settings):
    os.makedirs(settings)

# Load ProperTree.py's code. This will be written later.
print("Processing code...")
with open(dir / "ProperTree.py", 'r') as file:
    code = file.read()

# Load linux-app.c's code so we can embed main.sh into it.
with open(scripts / "linux-app.c", 'r') as file:
    ccode = file.read() # This isn't a typo; "code" was already taken

def copy_settings_json():
    print("Copying settings.json...")
    shutil.copy(scripts / "settings.json", settings / "settings.json")

# Here, we're gonna transfer settings.json to our new settings directory.
if os.path.exists(scripts / "settings.json"):
    # If the file already exists, then ask the user if they want to overwrite it.
    if os.path.exists(settings / "settings.json") and "--always-overwrite" not in args:
        while True:
            response = input(f"Do you want to overwrite {settings / "settings.json"}? (y/n/c): >> ").strip().lower()
            if response == 'y':
                copy_settings_json()
                break
            elif response == 'n':
                break
            elif response == 'c': # Quit
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

# If the user decided to use the existing payload (for debugging), but ProperTree.py isn't found, then we tell them and exit.
# The other scripts normally packaged into /payload/Scripts will have errors at runtime if not present, so it's not our problem.
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

# Copy all the assets.
if "--use-existing-payload" not in args:
    print("Copying assets...")
    for x in os.listdir(scripts):
        if x.startswith(".") or not x.lower().endswith((".py",".plist","version.json")):
            continue
        copy_asset(x)

# Compress the payload into a .tar.gz.
print("Creating payload...")
with tarfile.open(dist / "payload.tar.gz", "w:gz") as tar:
    for dirpath, dirnames, filenames in os.walk(payload_dir):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            tar.add(filepath, arcname=os.path.relpath(filepath, payload_dir))

# Here's where we add the payload. We cat payload.tar.gz into main.sh, which uses the delimiter "BREAKER" to decide where the binary is.
result = subprocess.run(f"cat {dist}/payload.tar.gz >> {dist}/main.sh", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if result.returncode != 0:
    print(f"Error: {result.stderr}")

# Here's where we create install.sh by adding a payload here too. The payload is just main.sh, uncompressed.
with open(dist / "install.sh", 'wb') as file, open(dist / "main.sh", 'rb') as main_file:
    file.write(install_script.encode('utf-8') + main_file.read())

# These next couple sections is processing and copying main.sh and install.sh.
print("Copying scripts...")

subprocess.run(["chmod", "+x", f"{dist}/main.sh"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if result.returncode != 0:
    print(f"Error: {result.stderr}")
subprocess.run(["chmod", "+x", f"{dist}/install.sh"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if result.returncode != 0:
    print(f"Error: {result.stderr}")

shutil.copy(dist / "main.sh", result_dir / "ProperTree.sh")
shutil.copy(dist / "install.sh", result_dir / f"ProperTree-Installer-{version}.sh")

if "--skip-compile" not in args:
    print("Embedding script...")
    with open(dist / 'main.sh', 'rb') as file:
        binary = file.read()
        bytes = [f"0x{byte:02X}" for byte in binary]
    
    with open(dist / 'main.c', 'w') as file:
        file.write(ccode.replace('const unsigned char shell_script[] = {};', f'const unsigned char shell_script[] = {{\n    {', '.join(bytes)}\n}};'))

    print("Generating executable...")
    try:
        # Run gcc, a C compiler. main.c is the generated source code, and it can be compiled manually to ARM or any other architecture.
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