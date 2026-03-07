"""
OSINTNEWS — Entry point.
Launches the GUI by default.
Use --cli flag to run in terminal mode instead.
"""

import sys


def main():
    if "--cli" in sys.argv:
        sys.argv.remove("--cli")
        from osintnews_cli import main as cli_main
        cli_main()
    else:
        try:
            import tkinter as tk
        except ImportError:
            print("[!] tkinter not available. Falling back to CLI mode.")
            from osintnews_cli import main as cli_main
            cli_main()
            return

        from modules.gui.app import launch
        launch()


if __name__ == "__main__":
    main()
