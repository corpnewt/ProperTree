import downloader
import json, os, sys, argparse

DEFAULT_URL = "https://raw.githubusercontent.com/corpnewt/ProperTree/master/Scripts/version.json"
DEFAULT_TEX_URL = "https://raw.githubusercontent.com/acidanthera/OpenCorePkg/master/Docs/Configuration.tex"
DL = None
try: DL = downloader.Downloader()
except: pass

def _print_output(output):
    print(json.dumps(output,indent=2))

def _get_latest_tex(url = None, file_path = None):
    if DL is None:
        return _print_output({
            "exception":"An Error Occurred Initializing The Downloader",
            "error":"Could not initialize the downloader."
        })
    url = url or DEFAULT_TEX_URL
    if file_path is None:
        return _print_output({
            "exception":"Target file path was not resolved, nor explicitly provided",
            "error":"Missing required arguments."
        })
    # We should have a target path and a URL - let's download
    try:
        file_path = DL.stream_to_file(url,file_path,False)
    except:
        return _print_output({
            "exception":"Could not get the Configuration.tex from github.  Potentially a network issue.",
            "error":"An Error Occurred Downloading Configuration.tex"
        })
    # Ensure the path exists
    if not os.path.isfile(file_path):
        return _print_output({
            "exception":"Could not get the Configuration.tex from github.  Potentially a network issue.",
            "error":"An Error Occurred Downloading Configuration.tex"
        })
    _print_output({
        "json":file_path
    })

def _check_for_update(version_url = None):
    if DL is None:
        return _print_output({
            "exception":"Could not initialize the downloader.",
            "error":"An Error Occurred Initializing The Downloader"
        })
    version_url = version_url or DEFAULT_URL
    try:
        json_string = DL.get_string(version_url,False)
    except:
        return _print_output({
            "exception":"Could not get version data from github.  Potentially a network issue.",
            "error":"An Error Occurred Checking For Updates"
        })
    try:
        json_data = json.loads(json_string)
    except:
        return _print_output({
            "exception":"Could not serialize returned JSON data.",
            "error":"An Error Occurred Checking For Updates"
        })
    _print_output({
        "json":json_data
    })

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog="update_check.py")
    parser.add_argument("-u", "--url", help="overrides the default URL for update/tex checks")
    parser.add_argument("-m", "--update-mode", help="sets the current update mode (update, or tex) - default is update", choices=["update","tex"])
    parser.add_argument("-t", "--tex-path", help="sets the preferred Configuration.tex path (required if using -m tex)")

    args = parser.parse_args()

    if not args.update_mode or args.update_mode == "update":
        _check_for_update(version_url=args.url)
    elif args.update_mode == "tex":
        if not args.tex_path:
            _print_output({
                "exception":"--tex-path is required when using -m tex",
                "error":"Missing Required Arguments"
            })
        else:
            _get_latest_tex(url=args.url,file_path=args.tex_path)
    else:
        _print_output({
            "exception":"No valid --update-mode was passed.",
            "error":"Invalid Arguments"
        })
