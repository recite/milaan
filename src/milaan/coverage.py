"""Check the catalogue against what replication archives actually call.

The claim this module exists to keep honest: comparisons are chosen by usage, not
by taste. That is easy to assert in a README and easy to drift away from, since
the interesting-looking procedure and the widely-used one are rarely the same.

So every spec declares what it `covers`, and coverage is a join against a ranking
of the corpus. Declared rather than inferred, deliberately: guessing which
procedure a spec exercises by matching identifiers in its expression is exactly
the technique that, applied to changelog prose in the sibling project, attributed
`Matrix` to three thousand scripts that meant base R. A short expression is more
tractable than prose, but `q(1)` -- a spec that aliases `quantile` in its setup --
would still be missed, and a coverage report that quietly undercounts is worse
than none.

Uncovered high-usage procedures are the work queue, in order.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field, replace
from pathlib import Path

from milaan.schema import CaseSpec

#: Names that move data rather than compute a number a paper reports. The corpus
#: ranking is led by them -- `length` at 3,268 scripts, `names` at 1,954 -- partly
#: because they are genuinely ubiquitous and partly because several CRAN packages
#: re-export base R's, so the frame credits them to `Matrix` or `raster`.
#:
#: Excluded from the coverage denominator, not from the catalogue: a spec about
#: `nrow` would agree trivially and teach nothing, and counting it as an uncovered
#: procedure makes the work queue look longer than it is. Coercion, reshaping,
#: indexing, counting, and plotting only -- anything that estimates a quantity
#: stays in scope, including `mean` and `log`.
PLUMBING = {
    # counting and shape
    "length",
    "nrow",
    "ncol",
    "dim",
    "nchar",
    "seq",
    "seq_len",
    "seq_along",
    # coercion
    "as.numeric",
    "as.character",
    "as.integer",
    "as.matrix",
    "as.vector",
    "as.data.frame",
    "as.factor",
    "as.logical",
    "as.Date",
    "factor",
    "numeric",
    "character",
    "integer",
    "matrix",
    "data.frame",
    "list",
    "vector",
    # reshaping and combining
    "cbind",
    "rbind",
    "c",
    "merge",
    "split",
    "unlist",
    "do.call",
    "t",
    "apply",
    "sapply",
    "lapply",
    "mapply",
    "vapply",
    "Reduce",
    "rapply",
    # indexing, ordering, membership
    "which",
    "which.max",
    "which.min",
    "match",
    "order",
    "sort",
    "rev",
    "subset",
    "head",
    "tail",
    "unique",
    "duplicated",
    "rownames",
    "colnames",
    "names",
    "rep",
    "ifelse",
    "is.na",
    "na.omit",
    "complete.cases",
    "levels",
    "dimnames",
    "row.names",
    "as.list",
    "all.equal",
    "ungroup",
    "foreach",
    "diag",
    # text and display
    "paste",
    "paste0",
    "sprintf",
    "format",
    "print",
    "cat",
    "toupper",
    "tolower",
    "gsub",
    "sub",
    "grepl",
    "substr",
    "strsplit",
    "trimws",
    # input and output
    "read.csv",
    "write.csv",
    "readRDS",
    "saveRDS",
    "read_csv",
    "st_read",
    "load",
    "save",
    # plotting
    "ggplot",
    "aes",
    "plot",
    "lines",
    "points",
    "legend",
    "par",
    "hist",
    "barplot",
    "boxplot",
    "abline",
    "axis",
    "text",
    "dev.off",
    "pdf",
    "png",
}


@dataclass
class Procedure:
    """One row of the corpus ranking.

    Attributes:
        rank: Position in the frame, most-used first.
        language: `R` or `Python`.
        fname: Function name as scripts call it.
        packages: Packages exporting it, semicolon-joined in the source CSV.
        scripts: Distinct corpus scripts calling it.
        share: Fraction of parsed scripts in that language.
        covered_by: Comparison ids declaring they exercise it.
    """

    rank: int
    language: str
    fname: str
    packages: list[str]
    scripts: int
    share: float
    covered_by: list[str] = field(default_factory=list)

    @property
    def covered(self) -> bool:
        """Whether any comparison claims this procedure.

        Returns:
            True when at least one spec declares it.
        """
        return bool(self.covered_by)


def load_frame(path: Path) -> list[Procedure]:
    """Read the corpus ranking.

    Args:
        path: CSV written by the sibling project's frame builder.

    Returns:
        Procedures, most-used first.
    """
    with Path(path).open() as handle:
        return [
            Procedure(
                rank=int(row["rank"]),
                language=row["language"],
                fname=row["fname"],
                packages=row["packages"].split(";") if row["packages"] else [],
                scripts=int(row["scripts"]),
                share=float(row["share"]),
            )
            for row in csv.DictReader(handle)
        ]


@dataclass
class Coverage:
    """What the catalogue reaches, and what it does not.

    Attributes:
        procedures: The ranking, annotated with which comparisons cover each.
        undeclared: Names a spec claims to cover that the frame does not list.
            Usually a typo; occasionally a procedure the corpus never calls,
            which is worth knowing before writing more specs about it.
    """

    procedures: list[Procedure] = field(default_factory=list)
    undeclared: dict[str, list[str]] = field(default_factory=dict)

    def top(
        self, language: str, n: int, computing_only: bool = True
    ) -> list[Procedure]:
        """The n most-used procedures in one language.

        Args:
            language: `R` or `Python`.
            n: How many to return.
            computing_only: Drop data plumbing, which leads the raw ranking and
                would agree trivially.

        Returns:
            The head of that language's ranking.
        """
        rows = [p for p in self.procedures if p.language == language]
        if computing_only:
            rows = [p for p in rows if p.fname not in PLUMBING]
        return rows[:n]

    def rate(
        self, language: str, n: int, computing_only: bool = True
    ) -> tuple[int, int]:
        """Covered count out of the top n.

        Args:
            language: `R` or `Python`.
            n: Depth into the ranking.
            computing_only: Drop data plumbing from the denominator.

        Returns:
            A `(covered, total)` pair.
        """
        head = self.top(language, n, computing_only)
        return sum(1 for p in head if p.covered), len(head)


def measure(specs: list[CaseSpec], frame: list[Procedure]) -> Coverage:
    """Join the catalogue's declared coverage against the corpus ranking.

    Args:
        specs: Every parsed comparison.
        frame: The corpus ranking.

    Returns:
        The annotated ranking, plus any declared name the frame does not list.
    """
    # Copied rather than annotated in place. Mutating the caller's frame means a
    # second call double-counts every procedure, which is silent and looks like
    # coverage improving on its own.
    annotated = [replace(p, covered_by=[]) for p in frame]

    by_name: dict[str, list[Procedure]] = {}
    for procedure in annotated:
        by_name.setdefault(procedure.fname, []).append(procedure)

    undeclared: dict[str, list[str]] = {}
    for spec in specs:
        for name in spec.covers:
            if name not in by_name:
                undeclared.setdefault(name, []).append(spec.id)
                continue
            for procedure in by_name[name]:
                procedure.covered_by.append(spec.id)

    return Coverage(procedures=annotated, undeclared=undeclared)
