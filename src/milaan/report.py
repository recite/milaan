"""Render runs into a version-stamped markdown report and a machine-readable JSON.

Reports are deterministic: no timestamps, no run ids, no dict-order dependence. Two
runs of an unchanged suite produce byte-identical output, so `git diff` on the
report is exactly the set of things that changed about the world.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from milaan.compare import Comparison, compare_case, summarize
from milaan.oracles import check_certified, check_invariants
from milaan.runner import CaseRun

_VERDICT_MARK = {"AGREE": "=", "NUMERIC": "~", "DIVERGE": "!="}


def _fmt(value: float | None) -> str:
    """Format a number for the report at fixed width.

    Args:
        value: The number, or None.

    Returns:
        A 10-significant-digit representation, or an em dash.
    """
    if value is None:
        return "--"
    if value != value:  # NaN
        return "NaN"
    return f"{value:.10g}"


def _env_line(run: CaseRun) -> list[str]:
    """Render the environment block for a case.

    Args:
        run: The case run.

    Returns:
        Markdown lines describing each backend's language and package versions.
    """
    lines = []
    for result in run.results:
        env = result.env or {}
        packages = env.get("packages") or {}
        pkg = ", ".join(f"{k} {v}" for k, v in sorted(packages.items()))
        lang = f"{env.get('language', '?')} {env.get('version', '?')}"
        lines.append(f"- `{result.backend}` -- {lang}" + (f" ({pkg})" if pkg else ""))
    return lines


def render_case(run: CaseRun) -> tuple[str, list[Comparison]]:
    """Render one case to markdown.

    Args:
        run: The case run.

    Returns:
        The markdown section and the comparisons it reports.
    """
    spec = run.spec
    comparisons = compare_case(run.results, spec)
    invariants = check_invariants(run.results, spec.invariants)
    certified = check_certified(run.results, spec)

    out = [f"### `{spec.id}` -- {spec.title}", ""]
    out += _env_line(run)
    if run.data_sha256:
        out.append(f"- `data.csv` sha256 `{run.data_sha256[:16]}`")
    out.append("")

    errored = [r for r in run.results if r.status != "ok"]
    if errored:
        out.append("**Backends that did not return numbers**")
        out.append("")
        for result in errored:
            first_line = (result.error or "").strip().splitlines()
            detail = first_line[0] if first_line else "no detail"
            out.append(f"- `{result.backend}` -- {result.status}: {detail}")
        out.append("")

    ok = [r.backend for r in run.results if r.status == "ok"]
    if comparisons and ok:
        header = "| quantity | " + " | ".join(f"`{b}`" for b in ok)
        header += " | reldiff | verdict | outcome |"
        out += [header, "|" + "---|" * (len(ok) + 4)]
        for c in comparisons:
            cells = [_fmt(c.values.get(b)) for b in ok]
            mark = _VERDICT_MARK.get(c.verdict, c.verdict)
            flag = " **NEW**" if c.is_new_finding else ""
            if c.outcome == "RESOLVED":
                flag = " *resolved*"
            out.append(
                f"| `{c.quantity}` | "
                + " | ".join(cells)
                + f" | {c.max_reldiff:.2e} | {mark} | {c.outcome}{flag} |"
            )
        out.append("")

    referenced = [c for c in comparisons if c.reference]
    if referenced:
        # The per-implementation verdicts are the substance of a reference spec:
        # collapsed into one worst-of number they say "something diverged", which
        # is the opposite of the point. Read down this column and you get the
        # answer to "which Python call reproduces the R one".
        out += [
            f"**Against `{referenced[0].reference}`**",
            "",
            "| implementation | quantity | reldiff | verdict | |",
            "|---|---|---|---|---|",
        ]
        by_backend = {b.name: b for b in spec.backends}
        for c in referenced:
            for name, (verdict, outcome) in sorted(c.against_reference.items()):
                reldiff = c.pairwise.get((c.reference or "", name), 0.0)
                flag = " **NEW**" if outcome == "NEW_FINDING" else ""
                if outcome == "RESOLVED":
                    flag = " *resolved*"
                label = by_backend[name].label if name in by_backend else name
                out.append(
                    f"| `{name}` -- {label} | `{c.quantity}` | {reldiff:.2e} | "
                    f"{_VERDICT_MARK.get(verdict, verdict)} | {outcome}{flag} |"
                )
        out.append("")

        reasons = {
            b.name: b.reason for b in spec.backends if b.reason and b.expect != "AGREE"
        }
        if reasons:
            out += ["**Why they differ**", ""]
            for name, reason in sorted(reasons.items()):
                out.append(f"- `{name}` -- {' '.join(reason.split())}")
            out.append("")

    if spec.finding:
        found = spec.finding
        verdict = (
            f"reconcilable -- {found.reconciliation}"
            if found.reconcilable
            else "**not reconcilable**: no argument makes these agree"
        )
        out += [
            f"**Cause: {found.cause}** ({verdict})",
            "",
        ]
        if found.note:
            out += [" ".join(found.note.split()), ""]

    documented = [c for c in comparisons if c.reason and c.verdict != "AGREE"]
    if documented:
        out.append("**Why these differ**")
        out.append("")
        for c in documented:
            out.append(f"- `{c.quantity}` -- {' '.join((c.reason or '').split())}")
        out.append("")

    if certified:
        out += ["**Against certified values**", ""]
        out.append("| quantity | backend | observed | certified | digits | |")
        out.append("|---|---|---|---|---|---|")
        for chk in certified:
            digits = "exact" if chk.digits == float("inf") else f"{chk.digits:.1f}"
            out.append(
                f"| `{chk.quantity}` | `{chk.backend}` | {_fmt(chk.observed)} | "
                f"{_fmt(chk.certified)} | {digits} | "
                f"{'ok' if chk.passed else '**FAIL**'} |"
            )
        out.append("")

    if invariants:
        out += ["**Metamorphic invariants**", ""]
        for chk in invariants:
            state = "ok" if chk.passed else "**FAIL**"
            detail = chk.error or f"{_fmt(chk.observed)} vs {_fmt(chk.expected)}"
            out.append(f"- `{chk.backend}`: `{chk.expr}` -- {detail} {state}")
        out.append("")

    return "\n".join(out), comparisons


def render(runs: list[CaseRun]) -> str:
    """Render the full suite report.

    Args:
        runs: All case runs.

    Returns:
        Markdown for the whole report.
    """
    sections, all_comparisons = [], []
    for run in runs:
        section, comparisons = render_case(run)
        sections.append(section)
        all_comparisons.extend(comparisons)

    counts = summarize(all_comparisons)
    new = [c for c in all_comparisons if c.is_new_finding]

    head = [
        "# milaan -- cross-implementation report",
        "",
        f"{len(runs)} cases, {len(all_comparisons)} compared quantities.",
        "",
        "| outcome | n |",
        "|---|---|",
    ]
    for key in ("EXPECTED", "NEW_FINDING", "RESOLVED", "UNCOMPARABLE"):
        head.append(f"| {key} | {counts.get(key, 0)} |")
    head.append("")
    for key in ("AGREE", "NUMERIC", "DIVERGE"):
        head.append(f"- `{key}`: {counts.get(f'verdict:{key}', 0)} quantities")
    head.append("")

    if new:
        head += ["## Undocumented divergences", ""]
        for c in new:
            head.append(
                f"- `{c.quantity}` -- observed {c.verdict}, expected {c.expected} "
                f"(reldiff {c.max_reldiff:.2e})"
            )
        head.append("")

    head += render_porting_table(runs)

    return "\n".join([*head, "## Cases", "", *sections]).rstrip() + "\n"


def render_porting_table(runs: list[CaseRun]) -> list[str]:
    """Summarise every documented finding as porting advice.

    The point of the catalogue rather than a by-product of it: someone
    reimplementing an R analysis in Python wants one table telling them which
    calls need an argument and which cannot be ported at all. Everything here is
    asserted elsewhere in the report -- each reconciliation is a comparison that
    had to come out `AGREE` for the run to pass.

    Args:
        runs: All case runs.

    Returns:
        Markdown lines, or an empty list when nothing documents a finding.
    """
    documented = [(r.spec, r.spec.finding) for r in runs if r.spec.finding]
    if not documented:
        return []

    out = [
        "## Porting table",
        "",
        "What to change when moving an analysis between the two languages.",
        "",
        "| comparison | cause | what to do |",
        "|---|---|---|",
    ]
    # Irreducible first: those are the ones no amount of care fixes, so they are
    # what a reader most needs to see before planning a port.
    order = {"IRREDUCIBLE": 0, "BUG": 1, "DEFAULT": 2, "DEFINITION": 3, "ALGORITHM": 4}
    for spec, found in sorted(
        documented, key=lambda pair: (order.get(pair[1].cause, 9), pair[0].id)
    ):
        advice = (
            " ".join(found.reconciliation.split())
            if found.reconcilable
            else "**cannot be reconciled**"
        )
        out.append(f"| `{spec.id}` | {found.cause} | {advice} |")
    out.append("")
    return out


def write(runs: list[CaseRun], directory: Path) -> tuple[Path, Path]:
    """Write `latest.md` and `latest.json`.

    Args:
        runs: All case runs.
        directory: Output directory.

    Returns:
        Paths to the markdown and JSON reports.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    md_path = directory / "latest.md"
    md_path.write_text(render(runs))

    payload = [
        {
            "case_id": run.spec.id,
            "family": run.spec.family,
            "title": run.spec.title,
            "data_sha256": run.data_sha256,
            "results": [r.to_dict() for r in run.results],
            "comparisons": [
                {
                    **asdict(c),
                    "pairwise": {f"{a}|{b}": v for (a, b), v in c.pairwise.items()},
                }
                for c in compare_case(run.results, run.spec)
            ],
        }
        for run in runs
    ]
    json_path = directory / "latest.json"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return md_path, json_path
