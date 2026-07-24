"""Non-invasive LLM capability-spike configuration check."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping


REQUIRED_ENV = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")


def check_config(environ: Mapping[str, str]) -> dict[str, object]:
    """Return secret-free readiness for the configured OpenAI-compatible LLM."""

    missing = sorted(name for name in REQUIRED_ENV if not environ.get(name))
    return {
        "status": "ready" if not missing else "unverified",
        "live_spike_ready": not missing,
        "required_variables": list(REQUIRED_ENV),
        "missing": missing,
        "secret_values_emitted": False,
        "network_calls_made": False,
        "streaming_included": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-config", action="store_true")
    args = parser.parse_args()
    if not args.check_config:
        parser.error("only --check-config is supported by this non-invasive spike")
    print(json.dumps(check_config(os.environ), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
