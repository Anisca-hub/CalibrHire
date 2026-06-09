import streamlit.web.cli as stcli
import os, sys

def resolve_path(path):
    basedir = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(basedir, path)

if __name__ == "__main__":
    # This simulates "streamlit run app.py"
    sys.argv = [
        "streamlit",
        "run",
        resolve_path("app.py"),
        "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())