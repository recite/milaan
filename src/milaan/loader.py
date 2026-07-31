"""Discover comparisons and parse them into `CaseSpec`.

Two file formats, one object. A **case** is a directory of hand-written backend
scripts and a `case.yaml`, which is what a comparison needs when it has real
setup -- fitting a Firth logistic regression, or running four estimators over one
design matrix. A **spec** is a single YAML file naming an expression per
implementation, which is what almost every comparison actually needs, and which
costs four lines instead of a hundred and fifty.

Specs compile down to cases: each implementation becomes a `BackendSpec` invoking
the generic evaluator for its language. Nothing downstream -- the runner, the
comparator, the report -- knows which format a comparison came from.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from milaan.schema import (
    CAUSES,
    BackendSpec,
    CaseSpec,
    Finding,
    Invariant,
    QuantitySpec,
)

#: Evaluators that turn an expression plus a dataset into the standard result
#: JSON. Relative to the repository root, resolved by `runner` through
#: `MILAAN_LIB`'s sibling.
EVALUATORS = {"R": "backends/eval_r.R", "Python": "backends/eval_py.py"}

#: How a language's evaluator is launched.
LAUNCHERS = {"R": ["Rscript", "--vanilla"], "Python": ["python"]}


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


def _parse_finding(raw: dict[str, Any] | None, case_id: str) -> Finding | None:
    """Parse the `finding` block.

    Args:
        raw: The `finding` mapping from YAML, if present.
        case_id: Case identifier, for error messages.

    Returns:
        The finding, or None when the spec documents none.

    Raises:
        CaseError: If the cause is unrecognised, or a disagreement is claimed
            reconcilable without saying how.
    """
    if not raw:
        return None
    cause = str(raw.get("cause", "")).upper()
    if cause not in CAUSES:
        raise CaseError(
            f"{case_id}: cause {cause!r} is not one of {', '.join(CAUSES)}. "
            "'They differ' is not a finding; the cause is what makes it one."
        )
    finding = Finding(
        cause=cause,
        reconcilable=bool(raw.get("reconcilable", False)),
        reconciliation=raw.get("reconciliation", ""),
        note=raw.get("note", ""),
    )
    if finding.reconcilable and not finding.reconciliation:
        raise CaseError(
            f"{case_id}: claims the disagreement is reconcilable but does not say "
            "how. The reconciliation is the deliverable -- a porting instruction "
            "someone can act on -- and 'yes, somehow' is not one."
        )
    if finding.cause == "IRREDUCIBLE" and finding.reconcilable:
        raise CaseError(
            f"{case_id}: cause is IRREDUCIBLE but reconcilable is true. "
            "Irreducible means no argument makes them agree."
        )
    return finding


def _implementation_backends(
    raw: dict[str, Any], case_id: str, root: Path
) -> list[BackendSpec]:
    """Compile an `implementations` block into backends.

    Each implementation names a language and an expression. The expression is
    passed to that language's generic evaluator, so a spec carries no code of its
    own -- which is the whole point, since a hand-written backend costs about a
    hundred and fifty lines and a spec entry costs one.

    Args:
        raw: The `implementations` mapping from YAML.
        case_id: Case identifier, for error messages.
        root: Repository root, against which evaluator paths resolve.

    Returns:
        One backend per implementation, in declaration order.

    Raises:
        CaseError: On an unknown language, a missing expression, or an expected
            divergence with no reason.
    """
    backends = []
    for name, body in raw.items():
        body = body or {}
        lang = str(body.get("lang", "")).strip()
        if lang not in EVALUATORS:
            raise CaseError(
                f"{case_id}: implementation {name!r} has language {lang!r}; "
                f"known languages are {', '.join(sorted(EVALUATORS))}"
            )
        expr = body.get("expr")
        if not expr:
            raise CaseError(f"{case_id}: implementation {name!r} has no expr")

        cmd = [*LAUNCHERS[lang], str(root / EVALUATORS[lang]), "--expr", str(expr)]
        if body.get("setup"):
            cmd += ["--setup", str(body["setup"])]

        spec = BackendSpec(
            name=name,
            cmd=cmd,
            label=body.get("label", f"{lang}: {expr}"),
            optional=bool(body.get("optional", False)),
            expect=str(body.get("expect", "AGREE")).upper(),
            reason=body.get("reason"),
        )
        if spec.expect != "AGREE" and not spec.reason:
            raise CaseError(
                f"{case_id}: implementation {name!r} expects {spec.expect} but "
                "gives no reason. An expected divergence without a documented "
                "cause is indistinguishable from an unexplained one."
            )
        backends.append(spec)
    return backends


def load_spec(path: Path, root: Path | None = None) -> CaseSpec:
    """Parse a declarative spec file.

    Args:
        path: Path to the spec YAML.
        root: Repository root, for locating evaluators and datasets. Defaults to
            two levels above the spec's directory (`specs/<family>/<id>.yaml`).

    Returns:
        The parsed specification, indistinguishable downstream from a case.

    Raises:
        CaseError: If the spec is malformed, names no implementations, or names
            a reference that is not one of them.
    """
    path = Path(path)
    root = Path(root) if root else path.resolve().parents[2]
    raw = yaml.safe_load(path.read_text()) or {}
    case_id = raw.get("id", path.stem)

    implementations = raw.get("implementations") or {}
    if not implementations:
        raise CaseError(f"{case_id}: declares no implementations")
    backends = _implementation_backends(implementations, case_id, root)

    reference = raw.get("reference")
    if reference and reference not in implementations:
        raise CaseError(
            f"{case_id}: reference {reference!r} is not one of the "
            f"implementations ({', '.join(implementations)})"
        )

    return CaseSpec(
        id=case_id,
        title=raw.get("title", case_id),
        family=raw.get("family", path.parent.name),
        directory=path.parent,
        backends=backends,
        quantities=_parse_quantities(raw.get("quantities", {}), case_id),
        certified={k: float(v) for k, v in (raw.get("certified") or {}).items()},
        agree_tol=float(raw.get("agree_tol", 1e-8)),
        numeric_tol=float(raw.get("numeric_tol", 1e-5)),
        reference=reference,
        finding=_parse_finding(raw.get("finding"), case_id),
        # Datasets are shared across specs rather than generated per comparison,
        # so two specs about the same procedure are measured on the same numbers
        # and their results can be read side by side.
        data_path=root / "datasets" / f"{raw['dataset']}.csv"
        if raw.get("dataset")
        else None,
        covers=list(raw.get("covers") or []),
    )


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
        covers=list(raw.get("covers") or []),
    )


#: Keys that only a spec has. A root can hold YAML that is not a comparison at
#: all -- kasauti's bug records live beside their cases as `bug.yaml` -- so
#: discovery asks whether a file is spec-shaped before trying to parse it as one.
SPEC_MARKERS = ("implementations", "reference", "finding")


def _is_spec(path: Path) -> bool:
    """Whether a YAML file is a comparison spec rather than something else.

    Deliberately not "any YAML that is not a case.yaml": a spec root may hold
    unrelated documents. But a file carrying *some* spec vocabulary and no
    `implementations` is a spec with a mistake in it, and is reported rather
    than skipped -- silently dropping a misspelled spec would mean a comparison
    that quietly never runs.

    Args:
        path: Candidate file.

    Returns:
        True when the file should be parsed as a spec.

    Raises:
        CaseError: If the file looks like a spec but declares no
            implementations.
    """
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise CaseError(f"{path}: not readable as YAML: {exc}") from exc
    if not isinstance(raw, dict):
        return False
    if "implementations" in raw:
        return True
    if any(key in raw for key in SPEC_MARKERS):
        raise CaseError(f"{path}: looks like a spec but declares no implementations")
    return False


def discover_cases(*roots: Path) -> list[CaseSpec]:
    """Find and parse every comparison under one or more root directories.

    Both formats are discovered together and become the same object: a
    `case.yaml` beside its backend scripts, and a standalone `*.yaml` spec whose
    implementations compile to evaluator invocations. Nothing downstream
    distinguishes them.

    Args:
        *roots: Directories to search. Missing directories are skipped.

    Returns:
        Parsed comparisons sorted by family then id.
    """
    cases = []
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        cases.extend(load_case(p.parent) for p in sorted(root.rglob("case.yaml")))
        for path in sorted(root.rglob("*.yaml")):
            if path.name != "case.yaml" and _is_spec(path):
                cases.append(load_spec(path))
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
