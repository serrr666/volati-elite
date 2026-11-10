import argparse

import uvicorn


def main():
    if "--no-browser" not in __import__("sys").argv and "--web" not in __import__("sys").argv:
        from .desktop import main as desktop_main
        return desktop_main()
    parser = argparse.ArgumentParser(description="volati elite — local memory forensics workbench")
    parser.add_argument("--web",action="store_true")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    import json,os
    from . import db,__version__
    from .security import API_TOKEN
    db.DATA.mkdir(parents=True,exist_ok=True)
    (db.DATA/'desktop-ready.json').write_text(json.dumps({'port':args.port,'pid':os.getpid(),'version':__version__,'token':API_TOKEN}),encoding='utf8')
    uvicorn.run("volstudio.app:app", host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
