"""Entrypoint for a single container host."""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from jd_agent.container.registry import ContainerKind, create_runner

_REPO_ROOT = Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> None:
    """Load env and run the selected container until it stops."""

    load_dotenv(_REPO_ROOT / ".env")
    parser = argparse.ArgumentParser(prog="jd-agent-container")
    parser.add_argument(
        "--container",
        choices=[kind.value for kind in ContainerKind],
        default=ContainerKind.SQS.value,
        help="Host implementation to run (default: sqs)",
    )
    args = parser.parse_args(argv)
    create_runner(args.container).run()


if __name__ == "__main__":
    main()
