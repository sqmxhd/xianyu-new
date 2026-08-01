"""Backward-compatible wrapper for the database bootstrap helper."""

try:
    from tools.ensure_database import main
except ModuleNotFoundError:  # Direct execution from the tools directory.
    from ensure_database import main


if __name__ == "__main__":
    raise SystemExit(main())
