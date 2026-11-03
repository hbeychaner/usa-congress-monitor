"""Check local Compose capacity without starting, stopping or changing services."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.config.local_capacity import LocalCapacityPolicy
from cdm.deployment.capacity import DockerCapacityProbe


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", default="operations")
    args = parser.parse_args()
    profiles = [name.strip() for name in args.profiles.split(",") if name.strip()]
    try:
        report = DockerCapacityProbe(
            Path(__file__).resolve().parents[1], LocalCapacityPolicy()
        ).inspect(profiles)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        parser.exit(
            2,
            "Capacity check could not read Docker/Compose metadata; startup refused.\n",
        )
    except ValidationError:
        parser.exit(
            2,
            "Capacity check received invalid Docker/Compose resource metadata; startup refused.\n",
        )
    print(report.model_dump_json(indent=2))
    return 0 if report.admitted else 1


if __name__ == "__main__":
    sys.exit(main())
