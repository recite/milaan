"""Command-line entry point."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from milaan import report as report_module
from milaan.compare import compare_case
from milaan.loader import discover_cases, select_cases
from milaan.runner import DEFAULT_TIMEOUT, run_case

ROOT = Path(__file__).resolve().parents[2]

#: Where comparisons live. `specs/` holds the declarative catalogue -- one YAML
#: per procedure, no backend scripts -- and `cases/` holds the handful that need
#: real setup code and so are written out longhand.
CASE_ROOTS = [ROOT / "specs", ROOT / "cases"]


@click.group()
@click.version_option()
def main() -> None:
    """Do R and Python agree? Measure it."""


@main.command("list")
@click.option("--cases-dir", type=click.Path(path_type=Path), default=None)
def list_cases(cases_dir: Path | None) -> None:
    """List discovered cases.

    Args:
        cases_dir: Directory holding case definitions.
    """
    for case in discover_cases(*([cases_dir] if cases_dir else CASE_ROOTS)):
        backends = ",".join(b.name for b in case.backends)
        click.echo(f"{case.family:16} {case.id:28} [{backends}]  {case.title}")


@main.command()
@click.argument("names", nargs=-1)
@click.option("--all", "run_all", is_flag=True, help="Run every case.")
@click.option("--cases-dir", type=click.Path(path_type=Path), default=None)
@click.option(
    "--reports-dir", type=click.Path(path_type=Path), default=ROOT / "reports"
)
@click.option("--timeout", default=DEFAULT_TIMEOUT, show_default=True)
@click.option(
    "--strict",
    is_flag=True,
    help="Exit non-zero if any quantity diverges more than the case documents.",
)
def run(
    names: tuple[str, ...],
    run_all: bool,
    cases_dir: Path | None,
    reports_dir: Path,
    timeout: int,
    strict: bool,
) -> None:
    """Run cases and write a report.

    Args:
        names: Case ids or family names. Ignored when `run_all` is set.
        run_all: Run every discovered case.
        cases_dir: Directory holding case definitions.
        reports_dir: Where to write `latest.md` and `latest.json`.
        timeout: Per-process timeout in seconds.
        strict: Exit non-zero on any undocumented divergence.
    """
    roots = [cases_dir] if cases_dir else CASE_ROOTS
    selected = select_cases(roots, [] if run_all else list(names))
    if not selected:
        click.echo("no cases selected", err=True)
        sys.exit(1)

    runs, new_findings = [], []
    for spec in selected:
        click.echo(f"running {spec.id} ... ", nl=False)
        case_run = run_case(spec, timeout=timeout)
        runs.append(case_run)

        comparisons = compare_case(case_run.results, spec)
        fresh = [c for c in comparisons if c.is_new_finding]
        new_findings.extend(fresh)
        errored = [r.backend for r in case_run.results if r.status == "error"]

        state = f"{len(comparisons)} quantities"
        if fresh:
            state += f", {len(fresh)} UNDOCUMENTED"
        if errored:
            state += f", errors in {','.join(errored)}"
        click.echo(state)

    md_path, json_path = report_module.write(runs, reports_dir)
    click.echo(f"\nwrote {md_path.relative_to(ROOT)} and {json_path.relative_to(ROOT)}")

    if new_findings:
        click.echo(f"\n{len(new_findings)} undocumented divergence(s):")
        for c in new_findings:
            click.echo(
                f"  {c.quantity}: observed {c.verdict}, expected {c.expected} "
                f"(reldiff {c.max_reldiff:.2e})"
            )
        if strict:
            sys.exit(1)


@main.command()
@click.option("--cases-dir", type=click.Path(path_type=Path), default=None)
@click.option(
    "--frame", type=click.Path(path_type=Path), default=ROOT / "data/sampling_frame.csv"
)
@click.option("--language", type=click.Choice(["R", "Python"]), default="R")
@click.option("--top", type=int, default=30, show_default=True)
def coverage(cases_dir: Path | None, frame: Path, language: str, top: int) -> None:
    """Check the catalogue against what replication archives actually call.

    Args:
        cases_dir: Directory holding comparisons.
        frame: Corpus ranking CSV.
        language: Which language's ranking to report.
        top: How far down the ranking to look.
    """
    from milaan.coverage import load_frame, measure

    specs = discover_cases(*([cases_dir] if cases_dir else CASE_ROOTS))
    result = measure(specs, load_frame(frame))
    covered, total = result.rate(language, top)

    click.echo(
        f"{covered} of the top {total} {language} procedures by corpus usage "
        f"are covered by {len(specs)} comparisons\n"
    )
    click.echo(f"{'#':>4} {'scripts':>8} {'procedure':22} covered by")
    for procedure in result.top(language, top):
        by = ", ".join(procedure.covered_by) if procedure.covered else "--"
        click.echo(
            f"{procedure.rank:>4} {procedure.scripts:>8} {procedure.fname:22} {by}"
        )

    if result.undeclared:
        click.echo(
            "\nDeclared but absent from the frame -- a typo, or a procedure the "
            "corpus never calls:"
        )
        for name, ids in sorted(result.undeclared.items()):
            click.echo(f"  {name} ({', '.join(ids)})")


@main.command()
@click.option("--cases-dir", type=click.Path(path_type=Path), default=None)
@click.option(
    "--reports-dir", type=click.Path(path_type=Path), default=ROOT / "reports"
)
def report(cases_dir: Path | None, reports_dir: Path) -> None:
    """Re-render the report from results already on disk, without re-running.

    Args:
        cases_dir: Directory holding case definitions.
        reports_dir: Where to write the report.
    """
    from milaan.runner import CaseRun
    from milaan.schema import Result

    runs = []
    for spec in discover_cases(*([cases_dir] if cases_dir else CASE_ROOTS)):
        results = []
        for backend in spec.backends:
            path = spec.directory / f"results.{backend.name}.json"
            if path.exists():
                results.append(Result.load(path))
        if results:
            runs.append(CaseRun(spec=spec, results=results))

    if not runs:
        click.echo("no results on disk; run `milaan run --all` first", err=True)
        sys.exit(1)

    md_path, _ = report_module.write(runs, reports_dir)
    click.echo(f"wrote {md_path}")
