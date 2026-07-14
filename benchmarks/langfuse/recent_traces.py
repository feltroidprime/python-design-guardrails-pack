#!/usr/bin/env python3
"""List recent local Langfuse traces through its public API."""

import argparse
import base64
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


HERE = Path(__file__).resolve().parent


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, separator, value = stripped.partition("=")
        if separator:
            values[name] = value
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=HERE / ".env")
    parser.add_argument("--base-url", default="http://127.0.0.1:3000")
    parser.add_argument("--minutes", type=int, default=60)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    if args.minutes <= 0 or not 1 <= args.limit <= 100:
        parser.error("--minutes must be positive and --limit must be between 1 and 100")
    try:
        env = _read_env(args.env_file)
        public_key = env["LANGFUSE_PUBLIC_KEY"]
        secret_key = env["LANGFUSE_SECRET_KEY"]
    except (OSError, KeyError) as error:
        print(
            f"cannot read Langfuse credentials from {args.env_file}: {error}",
            file=sys.stderr,
        )
        return 2

    since = datetime.now(timezone.utc) - timedelta(minutes=args.minutes)
    query = urlencode(
        {
            "limit": args.limit,
            "fromTimestamp": since.isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            ),
        }
    )
    token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode("ascii")
    request = Request(
        f"{args.base_url.rstrip('/')}/api/public/traces?{query}",
        headers={"Authorization": f"Basic {token}", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - operator-supplied URL
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"Langfuse trace query failed: {error}", file=sys.stderr)
        return 1

    traces = payload.get("data", [])
    if not traces:
        print(f"No traces in the last {args.minutes} minutes.")
        return 0
    print("TIMESTAMP\tNAME\tTRACE ID")
    for trace in traces:
        print(
            f"{trace.get('timestamp', '-')}\t{trace.get('name') or '-'}\t{trace.get('id', '-')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
