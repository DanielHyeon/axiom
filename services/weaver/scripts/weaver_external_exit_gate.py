from __future__ import annotations

import argparse
import os
import subprocess
import sys


def _enabled(value: str | None) -> bool:
    if not value:
        return False
    return value.lower() in {"1", "true", "yes", "on"}


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required env: {name}")
    return value


def _run_once(loop: int) -> None:
    cmd = [sys.executable, "-m", "pytest", "-q", "-rA", "tests/integration/test_external_modes_e2e.py"]
    print(f"[weaver-exit-gate] loop={loop} running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    print(out.strip())
    if proc.returncode != 0:
        raise RuntimeError(f"pytest failed at loop={loop}, rc={proc.returncode}")
    lower = out.lower()
    if "skipped" in lower:
        raise RuntimeError(f"integration test was skipped at loop={loop}; live gate requires non-skip execution")
    if "passed" not in lower:
        raise RuntimeError(f"integration test did not report pass at loop={loop}")
    if "failed" in lower:
        raise RuntimeError(f"integration test reported failure at loop={loop}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Weaver external live integration exit gate")
    parser.add_argument("--loops", type=int, default=2, help="number of repeated live test runs")
    args = parser.parse_args()

    if args.loops < 1:
        print("--loops must be >= 1", file=sys.stderr)
        return 2

    try:
        if not _enabled(os.getenv("WEAVER_RUN_E2E")):
            raise RuntimeError("WEAVER_RUN_E2E must be set to 1/true/yes/on")
        for name in ("MINDSDB_URL", "POSTGRES_DSN", "NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"):
            _require_env(name)
        for i in range(1, args.loops + 1):
            _run_once(i)
        print(f"[weaver-exit-gate] success loops={args.loops}")
        return 0
    except Exception as exc:  # pragma: no cover - gate script
        print(f"[weaver-exit-gate] failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
