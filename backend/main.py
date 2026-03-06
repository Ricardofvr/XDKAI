from __future__ import annotations

import argparse
import sys

from backend.bootstrap import bootstrap_application
from backend.config import ConfigError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Portable AI Drive PRO backend service")
    parser.add_argument(
        "--config",
        dest="config_path",
        default=None,
        help="Optional path to config JSON file",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        app = bootstrap_application(config_path=args.config_path)
    except ConfigError as exc:
        print(f"Startup failed: invalid configuration: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Startup failed: system error: {exc}", file=sys.stderr)
        return 3

    try:
        app.run()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
