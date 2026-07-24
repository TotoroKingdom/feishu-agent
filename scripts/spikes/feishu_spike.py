"""Non-invasive Feishu capability-spike configuration check.

This module intentionally does not call Feishu APIs. A live spike requires a
real sandbox and an explicit implementation of each approved probe; this
command only proves whether the required sandbox configuration is present.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping


REQUIRED_ENV = (
    "FEISHU_APP_ID",
    "FEISHU_APP_SECRET",
    "FEISHU_VERIFICATION_TOKEN",
    "FEISHU_ENCRYPT_KEY",
    "FEISHU_TEST_USER_OPEN_ID",
    "FEISHU_TEST_CHAT_ID",
    "FEISHU_TEST_BITABLE_APP_TOKEN",
    "FEISHU_TEST_BITABLE_TABLE_ID",
    "FEISHU_TEST_DOCUMENT_PARENT_TOKEN",
)


def check_config(environ: Mapping[str, str]) -> dict[str, object]:
    """Return a secret-free readiness result for a Feishu sandbox."""

    missing = sorted(name for name in REQUIRED_ENV if not environ.get(name))
    return {
        "status": "ready" if not missing else "unverified",
        "live_spike_ready": not missing,
        "required_variables": list(REQUIRED_ENV),
        "missing": missing,
        "secret_values_emitted": False,
        "network_calls_made": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="check for sandbox configuration without making network calls",
    )
    args = parser.parse_args()
    if not args.check_config:
        parser.error("only --check-config is supported by this non-invasive spike")

    print(json.dumps(check_config(os.environ), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
