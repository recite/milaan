"""Shared helpers for Python backend scripts.

Each backend script is a standalone program invoked as
`python3 run_py.py <data.csv> <out.json>`. Its only job is to write the result
schema. Failures are captured into `status: "error"` rather than raised, because
a package refusing to fit a model is a finding, not a harness problem.
"""

from __future__ import annotations

import csv
import importlib
import json
import math
import platform
import sys
import traceback
import warnings
from collections.abc import Callable
from typing import Any


def args() -> tuple[str, str]:
    """Return the data and output paths from argv.

    The runner appends both paths to whatever the case declared as the backend
    command, so they are always the last two arguments. Reading from the end lets
    one script serve several backends that differ only by a flag.

    Returns:
        A `(data_path, out_path)` pair.

    Raises:
        SystemExit: If the script was invoked with too few arguments.
    """
    if len(sys.argv) < 3:
        raise SystemExit("usage: python3 <script> [flags...] <data.csv> <out.json>")
    return sys.argv[-2], sys.argv[-1]


def env(packages: list[str]) -> dict[str, Any]:
    """Describe the interpreter and the versions of the packages in play.

    Args:
        packages: Importable module names to report versions for.

    Returns:
        The `env` block of the result schema.
    """
    versions = {}
    for name in packages:
        try:
            versions[name] = getattr(
                importlib.import_module(name), "__version__", "unknown"
            )
        except ImportError:
            versions[name] = "not installed"
    return {
        "language": "Python",
        "version": platform.python_version(),
        "packages": versions,
    }


def read_csv(path: str) -> dict[str, list[float]]:
    """Read a numeric CSV into column lists.

    Args:
        path: Path to the CSV.

    Returns:
        Column name to list of floats.
    """
    def value(raw: str) -> float:
        # R writes missing values as NA and both languages read NaN, so the two
        # sides of a comparison see the same gaps rather than one of them
        # refusing to parse the file.
        text = (raw or "").strip()
        return math.nan if text in ("", "NA", "NaN", "nan", "None") else float(text)

    with open(path, newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {key: [value(row[key]) for row in rows] for key in rows[0]}


def clean(quantities: dict[str, Any]) -> dict[str, float | None]:
    """Coerce quantities to JSON-safe floats.

    Non-finite values become `None`, which the comparison engine reads as "the
    backend produced this key but the value was undefined" -- distinct from not
    producing the key at all.

    Args:
        quantities: Raw quantity map.

    Returns:
        The same keys with float or None values.
    """
    out: dict[str, float | None] = {}
    for key, value in quantities.items():
        if value is None:
            out[key] = None
            continue
        number = float(value)
        out[key] = number if math.isfinite(number) else None
    return out


def main(
    case_id: str,
    backend: str,
    body: Callable[[str], dict[str, Any]],
    packages: list[str],
) -> None:
    """Run a backend body and write its result file.

    Args:
        case_id: Case identifier.
        backend: Backend name.
        body: Callable taking the data path and returning a dict with
            `quantities` and optionally `diagnostics`.
        packages: Module names whose versions to stamp into the result.
    """
    data_path, out_path = args()
    payload: dict[str, Any] = {
        "case_id": case_id,
        "backend": backend,
        "env": env(packages),
        "status": "ok",
        "quantities": {},
        "diagnostics": {},
        "error": None,
    }
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            result = body(data_path)
            payload["quantities"] = clean(result.get("quantities", {}))
            payload["diagnostics"] = result.get("diagnostics", {})
        except Exception:
            payload["status"] = "error"
            payload["error"] = traceback.format_exc(limit=3).strip()
        payload["diagnostics"]["warnings"] = [str(w.message) for w in caught]

    with open(out_path, "w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
