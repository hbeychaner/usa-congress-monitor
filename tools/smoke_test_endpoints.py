#!/usr/bin/env python3
"""Run consumer once for each SPECS endpoint and report success/failure."""

import subprocess
import os
from src.data_collection.queueing.specs import SPECS

ROOT = os.getcwd()
PYENV = os.environ.copy()
PYENV["PYTHONPATH"] = ROOT

results = {}
for endpoint in SPECS.keys():
    print(f"=== Testing {endpoint} ===")
    cmd = ["python", "orchestrators/sync/rabbitmq_consumer.py", endpoint, "--once"]
    try:
        proc = subprocess.run(cmd, env=PYENV, capture_output=True, text=True, timeout=6)
        out = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as e:

        def _to_str(x):
            if x is None:
                return ""
            if isinstance(x, bytes):
                return x.decode("utf-8", errors="replace")
            return x

        out = (
            _to_str(getattr(e, "stdout", None))
            + _to_str(getattr(e, "stderr", None))
            + "\n[ERROR] TimeoutExpired while running consumer\n"
        )
        proc = e
    ok = False
    if "Marked chunk as complete" in out or "Indexed" in out:
        ok = True
    returncode = getattr(proc, "returncode", -1)
    results[endpoint] = {"returncode": returncode, "ok": ok, "output": out}
    print(out)

print("\n=== Summary ===")
for ep, r in results.items():
    status = "OK" if r["ok"] and r["returncode"] == 0 else "FAIL"
    print(f"{ep}: {status} (rc={r['returncode']})")
