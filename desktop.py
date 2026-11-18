"""PyInstaller entry point; the public Python entry point uses the same dispatch."""
from studyframe.launcher import main

if __name__ == '__main__':
    raise SystemExit(main())
