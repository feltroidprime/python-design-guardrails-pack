#!/usr/bin/env python3
"""Create the ignored Langfuse environment file with local random secrets."""

import argparse
import os
from pathlib import Path
import secrets
import sys


HERE = Path(__file__).resolve().parent
SECRET_VALUES = {
    "POSTGRES_PASSWORD": lambda: secrets.token_hex(24),
    "CLICKHOUSE_PASSWORD": lambda: secrets.token_hex(24),
    "REDIS_AUTH": lambda: secrets.token_hex(24),
    "MINIO_ROOT_PASSWORD": lambda: secrets.token_hex(24),
    "SALT": lambda: secrets.token_hex(24),
    "ENCRYPTION_KEY": lambda: secrets.token_hex(32),
    "NEXTAUTH_SECRET": lambda: secrets.token_hex(32),
    "LANGFUSE_PUBLIC_KEY": lambda: f"pk-lf-{secrets.token_hex(16)}",
    "LANGFUSE_SECRET_KEY": lambda: f"sk-lf-{secrets.token_hex(16)}",
    "LANGFUSE_INIT_USER_PASSWORD": lambda: secrets.token_urlsafe(24),
}


def _render_example() -> str:
    lines: list[str] = []
    for line in (HERE / ".env.example").read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        if separator and name in SECRET_VALUES:
            value = SECRET_VALUES[name]()
        lines.append(f"{name}{separator}{value}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / ".env")
    args = parser.parse_args()

    try:
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print(f"refusing to overwrite: {args.output} already exists", file=sys.stderr)
        return 2
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(_render_example())
    except BaseException:
        args.output.unlink(missing_ok=True)
        raise
    print(f"created {args.output} (mode 0600)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
