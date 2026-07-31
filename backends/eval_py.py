"""Generic Python backend: evaluate an expression against a dataset.

    python eval_py.py --expr "np.std(x)" [--setup "..."] <data.csv> <out.json>

The dataset's columns are bound as names, so `np.std(x)` means the column called
x, and the whole frame is available as `d`. numpy, pandas, scipy.stats, and the
statsmodels and scikit-learn entry points are pre-imported under their
conventional aliases, because a spec should read like the code someone would
actually write.

On eval(): the expressions come from spec files in this repository, which are
reviewed like any other source. This is a test harness deliberately running the
code it is given -- the same trust boundary as the hand-written backend scripts
it replaces, which are simply executed. It must never be pointed at a spec from
an untrusted source.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Fallback is the source checkout; the runner normally sets MILAAN_LIB.
_LIB = Path(__file__).resolve().parents[1] / "src" / "milaan" / "lib"
sys.path.insert(0, os.environ.get("MILAAN_LIB", str(_LIB)))

import milaan_py as cc


def namespace() -> dict:
    """Build the evaluation namespace.

    Imports are attempted individually so a spec needing only numpy still runs on
    a machine without statsmodels, rather than the whole backend failing on an
    import it never uses.

    Returns:
        Module aliases available to every expression, plus `__modules__` listing
        the distributions actually imported.
    """
    space: dict = {}
    loaded: list[str] = []
    for alias, module in (
        ("np", "numpy"),
        ("pd", "pandas"),
        ("st", "scipy.stats"),
        ("sp", "scipy"),
        ("sm", "statsmodels.api"),
        ("smf", "statsmodels.formula.api"),
        ("sklearn", "sklearn"),
    ):
        try:
            space[alias] = __import__(module, fromlist=["__name__"])
        except ImportError:
            continue
        loaded.append(module.split(".")[0])
    # Versions are stamped by real module name, not by alias: reporting "np not
    # installed" for a run that used numpy would make the env block a liability.
    space["__modules__"] = sorted(set(loaded))
    return space


def flag(argv: list[str], name: str, default: str = "") -> str:
    """Read a `--name value` flag out of argv.

    Args:
        argv: Full argument vector.
        name: Flag to find, including the leading dashes.
        default: Value when the flag is absent.

    Returns:
        The flag's value, or `default`.
    """
    if name in argv:
        index = argv.index(name)
        if index + 1 < len(argv):
            return argv[index + 1]
    return default


def main() -> None:
    """Evaluate the expression and write the result."""
    expr = flag(sys.argv, "--expr")
    setup = flag(sys.argv, "--setup")
    if not expr:
        raise SystemExit("eval_py.py: --expr is required")

    space = namespace()

    def body(path: str) -> dict:
        env = {k: v for k, v in space.items() if k != "__modules__"}
        # A dataset is optional: an expression about random number generation, or
        # one over literals, has no columns to bind.
        if path and Path(path).exists() and Path(path).stat().st_size:
            columns = cc.read_csv(path)
            if "np" in space:
                columns = {
                    k: space["np"].asarray(v, dtype=float) for k, v in columns.items()
                }
            env.update(columns)
            if "pd" in space:
                env["d"] = space["pd"].DataFrame(columns)

        # Setup runs first and shares the namespace, so it can seed the RNG or
        # fit a model the expression then extracts from.
        if setup:
            exec(setup, env)

        raw = eval(expr, env)

        values = raw if hasattr(raw, "__len__") and not isinstance(raw, str) else [raw]
        values = [float(v) for v in values]
        if len(values) == 1:
            quantities = {"value": values[0]}
        else:
            quantities = {f"value.{i + 1}": v for i, v in enumerate(values)}
        return {
            "quantities": quantities,
            "diagnostics": {"expr": expr, "n": len(values)},
        }

    cc.main(
        case_id=os.environ.get("MILAAN_CASE", "spec"),
        backend=os.environ.get("MILAAN_BACKEND", "python"),
        body=body,
        packages=space["__modules__"],
    )


if __name__ == "__main__":
    main()
