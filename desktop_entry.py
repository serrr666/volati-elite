"""PyInstaller entry point. Worker modes are intentionally handled before importing Qt."""
from volstudio.desktop import main

if __name__ == "__main__":
    raise SystemExit(main())
