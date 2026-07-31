"""The result contract every backend writes and every comparison reads.

A backend is any process that can produce numbers for a case: an R script, a Python
script, or the same script run against a pinned older package version. All of them
emit the same JSON, which is what lets one comparison engine serve both the
cross-implementation suite and the changelog archaeology pipeline.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

Status = Literal["ok", "error", "skipped"]

#: A quantity absent from a backend's output. Distinct from `None` inside
#: `quantities`, which means the backend produced the key but the value was
#: undefined (NaN, non-convergence).
MISSING = object()


@dataclass
class Result:
    """One backend's answer for one case.

    Attributes:
        case_id: Identifier of the case this result belongs to.
        backend: Name of the backend, matching a `backends[].name` in `case.yaml`.
        env: Language, version, and package versions. Stamped into every report,
            because a finding is only meaningful relative to the versions it was
            observed on.
        status: `ok`, `error`, or `skipped`. An `error` is a *result*, not a
            harness failure: statsmodels refusing to fit a separated logit is
            exactly the behavior worth recording.
        quantities: Flat map of canonical name to value, e.g. `se.x@HC1`. A value
            of `None` means the backend produced the quantity but it was undefined.
        diagnostics: Free-form convergence flags, iteration counts, warnings.
        error: Exception text when `status == "error"`.
    """

    case_id: str
    backend: str
    env: dict[str, Any] = field(default_factory=dict)
    status: Status = "ok"
    quantities: dict[str, float | None] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the plain-dict form written to JSON.

        Returns:
            The dataclass as a JSON-serializable dict.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Result:
        """Build a `Result` from parsed JSON, ignoring unknown keys.

        Unknown keys are dropped rather than raising so that a backend script can
        add fields without breaking older drivers.

        Args:
            payload: Parsed JSON object.

        Returns:
            The corresponding `Result`.

        Raises:
            ValueError: If a required key is missing.
        """
        for required in ("case_id", "backend"):
            if required not in payload:
                raise ValueError(f"result is missing required key {required!r}")
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in payload.items() if k in known})

    @classmethod
    def load(cls, path: Path) -> Result:
        """Read a result from a JSON file.

        Args:
            path: Path to the JSON file.

        Returns:
            The parsed `Result`.
        """
        return cls.from_dict(json.loads(Path(path).read_text()))

    def dump(self, path: Path) -> None:
        """Write this result to a JSON file.

        Args:
            path: Destination path.
        """
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True))


@dataclass
class QuantitySpec:
    """What a case expects for one quantity.

    Attributes:
        expect: Expected verdict. `AGREE` is the default; anything else must be
            justified.
        reason: Why the divergence is expected. Required whenever `expect` is not
            `AGREE` -- an undocumented expected divergence is indistinguishable
            from a finding nobody bothered to explain.
        agree_tol: Override for the case-level agreement tolerance.
        numeric_tol: Override for the case-level numeric tolerance.
    """

    expect: str = "AGREE"
    reason: str | None = None
    agree_tol: float | None = None
    numeric_tol: float | None = None


@dataclass
class BackendSpec:
    """How to invoke one backend.

    Attributes:
        name: Backend name, used as the result filename suffix and report column.
        cmd: Argv template. The runner appends the data path and output path.
        label: Human-readable description for reports.
        optional: If true, a missing interpreter or package is a skip, not a
            failure. Used for backends behind an install that may not be present.
        expect: In a reference-relative spec, the verdict expected when this
            implementation is compared against the reference. Ignored when the
            case declares no reference.
        reason: Why this implementation is expected to diverge. Required whenever
            `expect` is not `AGREE`, for the same reason it is required on a
            quantity: an undocumented expected divergence is indistinguishable
            from a finding nobody explained.
    """

    name: str
    cmd: list[str]
    label: str = ""
    optional: bool = False
    expect: str = "AGREE"
    reason: str | None = None


@dataclass
class Invariant:
    """A metamorphic relation that must hold within a single backend's output.

    Metamorphic checks catch what cross-implementation agreement cannot: if two
    packages share a wrong formula they agree, but rescaling a predictor must
    still scale its coefficient exactly, in every implementation, or that
    implementation is wrong on its own terms.

    Attributes:
        expr: Arithmetic expression over quantity names, e.g.
            `"coef.x@scaled / coef.x"`.
        equals: Value the expression must take.
        tol: Absolute tolerance on the comparison.
        reason: What the relation encodes, for the report.
    """

    expr: str
    equals: float
    tol: float = 1e-10
    reason: str = ""


#: Why two implementations of the same procedure disagree. "They differ" is not
#: a finding; this is the field that makes it one, and the five values are
#: deliberately exhaustive over what the catalogue has met so far.
#:
#: * `DEFINITION` -- they compute different quantities. `sd` divides by `n-1`,
#:   `np.std` by `n`. Neither is wrong; they are not the same function.
#: * `DEFAULT` -- same quantity, different default option. `t.test` is Welch,
#:   `ttest_ind` is Student pooled.
#: * `ALGORITHM` -- same quantity and options, different numerical path. QR
#:   against normal equations on an ill-conditioned design.
#: * `IRREDUCIBLE` -- cannot agree by construction. Seeded RNG streams.
#: * `BUG` -- one of them is wrong on its own terms.
CAUSES = ("DEFINITION", "DEFAULT", "ALGORITHM", "IRREDUCIBLE", "BUG")


@dataclass
class Finding:
    """What a documented disagreement means, and whether it can be repaired.

    Attributes:
        cause: One of `CAUSES`.
        reconcilable: Whether some argument makes the implementations agree.
        reconciliation: The exact incantation that does it. Required when
            `reconcilable` is true -- this field is the deliverable, a porting
            instruction derived from measurement rather than from folklore, and
            "yes, somehow" is not one.
        note: Prose for the report.
    """

    cause: str
    reconcilable: bool = False
    reconciliation: str = ""
    note: str = ""


@dataclass
class CaseSpec:
    """A parsed `case.yaml`.

    Attributes:
        id: Case identifier, matching its directory name.
        title: One-line description.
        family: Grouping used in reports, e.g. `robust_se`.
        directory: Path to the case directory.
        backends: Backends to run.
        quantities: Per-quantity expectations.
        certified: Known-true values, e.g. from NIST StRD. Each backend is scored
            against these independently, which is what answers "who is wrong"
            when two backends disagree.
        invariants: Metamorphic relations.
        agree_tol: Relative difference below which two values are `AGREE`.
        numeric_tol: Relative difference below which a difference is attributed
            to algorithm or tolerance rather than to definition.
        notes: Path to `NOTES.md` if present.
        reference: Backend every other is compared against. Set by a spec whose
            question is directional -- *does the Python equivalent reproduce the
            R number* -- rather than "do these all agree". When set, expectations
            are declared per implementation instead of per quantity, so a spec
            can assert both that a default diverges and that a named argument
            reconciles it. When unset, the case falls back to all-pairs, which is
            right when no implementation is privileged.
        finding: The documented cause and reconciliation, if any.
        data_path: Dataset to feed the backends, when it lives outside the case
            directory. Specs share named datasets from `datasets/`; a longhand
            case generates its own `data.csv` beside itself.
    """

    id: str
    title: str
    family: str
    directory: Path
    backends: list[BackendSpec] = field(default_factory=list)
    quantities: dict[str, QuantitySpec] = field(default_factory=dict)
    certified: dict[str, float] = field(default_factory=dict)
    invariants: list[Invariant] = field(default_factory=list)
    agree_tol: float = 1e-8
    numeric_tol: float = 1e-5
    notes: str | None = None
    reference: str | None = None
    finding: Finding | None = None
    data_path: Path | None = None

    def spec_for(self, quantity: str) -> QuantitySpec:
        """Return the expectation for a quantity, defaulting to `AGREE`.

        Args:
            quantity: Canonical quantity name.

        Returns:
            The declared spec, or a default one expecting agreement.
        """
        return self.quantities.get(quantity, QuantitySpec())

    def tolerances_for(self, quantity: str) -> tuple[float, float]:
        """Return `(agree_tol, numeric_tol)` for a quantity.

        Args:
            quantity: Canonical quantity name.

        Returns:
            The per-quantity overrides where set, else the case defaults.
        """
        spec = self.spec_for(quantity)
        return (
            spec.agree_tol if spec.agree_tol is not None else self.agree_tol,
            spec.numeric_tol if spec.numeric_tol is not None else self.numeric_tol,
        )
