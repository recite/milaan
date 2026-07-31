"""Run a case: generate its data, invoke each backend, collect results.

Backends are separate processes exchanging JSON files. That keeps R and Python at
arm's length -- no `rpy2`, no shared interpreter state -- and means a pinned old
package version or a future Julia backend is just another command that writes the
same schema.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from milaan.schema import BackendSpec, CaseSpec, Result

#: Seconds before a backend is killed. Generous: some cases fit mixed models.
DEFAULT_TIMEOUT = 600

#: Shared backend helpers, exported to every backend as MILAAN_LIB. They live
#: inside the package rather than beside it so that they ship with the wheel: a
#: dependent project -- kasauti runs its version-regression cases through this
#: runner -- gets a working harness from an ordinary install, with no assumption
#: that the source tree is on disk.
LIB_DIR = Path(__file__).resolve().parent / "lib"


@dataclass
class CaseRun:
    """Everything produced by running one case.

    Attributes:
        spec: The case that was run.
        results: One result per backend, including synthesized error results for
            backends that crashed before writing JSON.
        data_sha256: Hash of the `data.csv` both backends read. Recorded so a
            reader can rule out "the two languages saw different data" as an
            explanation for any divergence.
        logs: Backend name to captured stderr, kept for debugging.
    """

    spec: CaseSpec
    results: list[Result]
    data_sha256: str | None = None
    logs: dict[str, str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        """Default the log map."""
        if self.logs is None:
            self.logs = {}


def sha256_file(path: Path) -> str:
    """Return the SHA-256 of a file.

    Args:
        path: File to hash.

    Returns:
        Lowercase hex digest.
    """
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_data(spec: CaseSpec, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    """Run the case's `data.py` to produce `data.csv`.

    Cases without a `data.py` build their data inside each backend script, which
    is appropriate when the data is a handful of literals.

    Args:
        spec: The case.
        timeout: Seconds before the generator is killed.

    Returns:
        SHA-256 of the generated `data.csv`, or None if the case has no generator.

    Raises:
        RuntimeError: If the generator fails or produces no `data.csv`.
    """
    if spec.data_path:
        # A spec points at a shared dataset it does not own, so there is nothing
        # to generate -- but the hash still travels with the run, which is what
        # rules out "the two languages saw different data" when they disagree.
        return sha256_file(spec.data_path) if spec.data_path.exists() else None
    generator = spec.directory / "data.py"
    if not generator.exists():
        return None

    proc = subprocess.run(  # noqa: S603
        ["python3", str(generator)],  # noqa: S607
        cwd=spec.directory,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{spec.id}: data.py failed\n{proc.stderr}")

    data = spec.directory / "data.csv"
    if not data.exists():
        raise RuntimeError(f"{spec.id}: data.py did not write data.csv")
    return sha256_file(data)


def run_backend(
    spec: CaseSpec,
    backend: BackendSpec,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[Result, str]:
    """Invoke one backend and read back its result.

    The backend is called as `<cmd...> <data.csv> <out.json>`. A backend that
    exits non-zero without writing JSON gets a synthesized `error` result rather
    than aborting the case: a package refusing to fit a model is a finding we want
    on the record next to the packages that did fit it.

    Args:
        spec: The case.
        backend: The backend to invoke.
        timeout: Seconds before the process is killed.

    Returns:
        A `(result, stderr)` pair.
    """
    out_path = spec.directory / f"results.{backend.name}.json"
    out_path.unlink(missing_ok=True)
    data_path = spec.data_path or spec.directory / "data.csv"

    cmd = [*backend.cmd, str(data_path), str(out_path)]
    # Backend scripts live at different depths under `cases/` and `bugs/`, so
    # the shared helper location is exported rather than reached by a relative
    # path. Moving a case between roots must not break it.
    env = {**os.environ, "MILAAN_LIB": str(LIB_DIR)}
    try:
        proc = subprocess.run(  # noqa: S603
            cmd,
            cwd=spec.directory,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
        stderr, returncode = proc.stderr, proc.returncode
    except FileNotFoundError as exc:
        status = "skipped" if backend.optional else "error"
        return (
            Result(
                case_id=spec.id,
                backend=backend.name,
                status=status,  # type: ignore[arg-type]
                error=f"interpreter not found: {exc}",
            ),
            str(exc),
        )
    except subprocess.TimeoutExpired:
        return (
            Result(
                case_id=spec.id,
                backend=backend.name,
                status="error",
                error=f"timed out after {timeout}s",
            ),
            "timeout",
        )

    if out_path.exists():
        result = Result.load(out_path)
        # Trust the file's own case_id/backend only as far as consistency allows;
        # the driver's view of which backend it invoked is authoritative.
        result.case_id, result.backend = spec.id, backend.name
        return result, stderr

    return (
        Result(
            case_id=spec.id,
            backend=backend.name,
            status="error",
            error=(
                f"exited {returncode} without writing {out_path.name}\n"
                f"{stderr.strip()[-2000:]}"
            ),
        ),
        stderr,
    )


def run_case(spec: CaseSpec, timeout: int = DEFAULT_TIMEOUT) -> CaseRun:
    """Generate data and run every backend for a case.

    Args:
        spec: The case to run.
        timeout: Per-process timeout in seconds.

    Returns:
        The collected run.
    """
    data_sha = generate_data(spec, timeout=timeout)
    results, logs = [], {}
    for backend in spec.backends:
        result, stderr = run_backend(spec, backend, timeout=timeout)
        results.append(result)
        if stderr.strip():
            logs[backend.name] = stderr.strip()
    return CaseRun(spec=spec, results=results, data_sha256=data_sha, logs=logs)
