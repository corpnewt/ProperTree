import downloader
import json, sys, argparse

DEFAULT_URL = "https://raw.githubusercontent.com/corpnewt/ProperTree/master/Scripts/version.json"
DL = None
try: DL = downloader.Downloader()
except: pass

def _print_output(output):
    print(json.dumps(output,indent=2))

def _check_for_update(version_url = None, user_initiated = False):
    if DL is None:
        return _print_output({
            "exception":"Could not initialize the downloader.",
            "error":"An Error Occurred Initializing The Downloader",
            "user_initiated":user_initiated
        })
    version_url = version_url or DEFAULT_URL
    try:
        json_string = DL.get_string(version_url,False)
    except:
        return _print_output({
            "exception":"Could not get version data from github.  Potentially a network issue.",
            "error":"An Error Occurred Checking For Updates",
            "user_initiated":user_initiated
        })
    try:
        json_data = json.loads(json_string)
    except:
        return _print_output({
            "exception":"Could not serialize returned JSON data.",
            "error":"An Error Occurred Checking For Updates",
            "user_initiated":user_initiated
        })
    _print_output({
        "json":json_data,
        "user_initiated":user_initiated
    })

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog="update_check.py")
    parser.add_argument("-u", "--url", help="the URL to check for updates")
    parser.add_argument("-i", "--user-initiated", help="sets the user_initiated return value to True", action="store_true")

    args = parser.parse_args()

    _check_for_update(version_url=args.url,user_initiated=args.user_initiated)