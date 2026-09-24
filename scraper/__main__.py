"""Package entrypoint."""

import sys


def main():
    # If launched without subcommands or via macOS Finder (-psn_...), default to GUI
    args = [a for a in sys.argv[1:] if not a.startswith("-psn")]
    if not args or args == ["gui"]:
        try:
            from scraper.gui import launch_gui
        except ImportError:
            from .gui import launch_gui
        launch_gui()
    else:
        try:
            from scraper.cli import cli
        except ImportError:
            from .cli import cli
        cli()


if __name__ == "__main__":
    main()
