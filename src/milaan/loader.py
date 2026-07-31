"""Discover case directories and parse their `case.yaml`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from milaan.schema import BackendSpec, CaseSpec, Invariant, QuantitySpec


class CaseError(ValueError):
    """Raised when a `case.yaml` is malformed or internally inconsistent."""


def _parse_quantities(raw: dict[str, Any], case_id: str) -> dict[str, QuantitySpec]:
    """Parse the `quantities` block, enforcing that divergence is justified.

    Args:
        raw: The `quantities` mapping from YAML.
        case_id: Case identifier, for error messages.

    Returns:
        Quantity name to spec.

    Raises:
        CaseError: If a non-agreeing expectation has no reason.
    """
    out = {}
    for name, body in (raw or {}).items():
        body = body or {}
        spec = QuantitySpec(
            expect=str(body.get("expect", "AGREE")).upper(),
            reason=body.get("reason"),
            agree_tol=body.get("agree_tol"),
            numeric_tol=body.get("numeric_tol"),
        )
        if spec.expect != "AGREE" and not spec.reason:
            raise CaseError(
                f"{case_id}: quantity {name!r} expects {spec.expect} but gives no "
                "reason. An expected divergence without a documented cause is "
                "indistinguishable from an unexplained one."
            )
        out[name] = spec
    return out


def load_case(directory: Path) -> CaseSpec:
    """Parse the `case.yaml` in a case directory.

    Args:
        directory: Directory containing `case.yaml`.

    Returns:
        The parsed case specification.

    Raises:
        CaseError: If the file is missing, malformed, or declares no backends.
    """
    directory = Path(directory)
    path = directory / "case.yaml"
    if not path.exists():
        raise CaseError(f"no case.yaml in {directory}")

    raw = yaml.safe_load(path.read_text()) or {}
    case_id = raw.get("id", directory.name)

    backends = [
        BackendSpec(
            name=b["name"],
            cmd=list(b["cmd"]),
            label=b.get("label", ""),
            optional=bool(b.get("optional", False)),
        )
        for b in raw.get("backends", [])
    ]
    if not backends:
        raise CaseError(f"{case_id}: declares no backends")

    names = [b.name for b in backends]
    if len(names) != len(set(names)):
        raise CaseError(f"{case_id}: duplicate backend names in {names}")

    invariants = [
        Invariant(
            expr=i["expr"],
            equals=float(i["equals"]),
            tol=float(i.get("tol", 1e-10)),
            reason=i.get("reason", ""),
        )
        for i in raw.get("invariants", [])
    ]

    notes = directory / "NOTES.md"
    return CaseSpec(
        id=case_id,
        title=raw.get("title", case_id),
        family=raw.get("family", directory.parent.name),
        directory=directory,
        backends=backends,
        quantities=_parse_quantities(raw.get("quantities", {}), case_id),
        certified={k: float(v) for k, v in (raw.get("certified") or {}).items()},
        invariants=invariants,
        agree_tol=float(raw.get("agree_tol", 1e-8)),
        numeric_tol=float(raw.get("numeric_tol", 1e-5)),
        notes=str(notes) if notes.exists() else None,
    )


def discover_cases(*roots: Path) -> list[CaseSpec]:
    """Find and parse every case under one or more root directories.

    Takes several roots because the two tracks live in separate trees: `cases/`
    holds cross-implementation comparisons, `bugs/` holds version regressions.
    A bug directory that has reached verification contains a `case.yaml` and is
    discovered here like any other; one that has not simply is not.

    Args:
        *roots: Directories to search. Missing directories are skipped.

    Returns:
        Parsed cases sorted by family then id.
    """
    cases = []
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        cases.extend(load_case(p.parent) for p in sorted(root.rglob("case.yaml")))
    return sorted(cases, key=lambda c: (c.family, c.id))


def select_cases(roots: Path | list[Path], wanted: list[str]) -> list[CaseSpec]:
    """Find cases by id or family name across one or more roots.

    Args:
        roots: A directory, or a list of them.
        wanted: Case ids or family names. Empty selects everything.

    Returns:
        Matching cases.

    Raises:
        CaseError: If a name matches nothing.
    """
    roots = [roots] if isinstance(roots, (str, Path)) else list(roots)
    cases = discover_cases(*roots)
    if not wanted:
        return cases
    selected = []
    for name in wanted:
        hits = [c for c in cases if c.id == name or c.family == name]
        if not hits:
            known = ", ".join(sorted({c.id for c in cases}))
            raise CaseError(f"no case or family named {name!r}. Known cases: {known}")
        selected.extend(h for h in hits if h not in selected)
    return selected
