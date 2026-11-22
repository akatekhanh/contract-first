#!/usr/bin/env python3
"""Audit a repo's contract bundle (contracts/*.yaml) for the defects that make a contract lie.

Checks, per repo:
  - bundle completeness: contracts/{business-spec,openapi,architecture}.yaml + schemas/
  - each spec YAML starts with a `# yaml-language-server: $schema=...` line
  - duplicate keys inside the same mapping (a parser silently keeps the last one)
  - YAML 1.1 implicit-typing hazards: bare NO/YES/ON/OFF/Y/N, version-like floats, bare dates
  - tabs used for indentation
  - required top-level sections per file
  - ADR rules: decided -> date + rationale; open -> resolution_criteria +
    default_if_unresolved; blocked_by -> an existing blocker id; files under an
    open ADR's `affects` must not exist yet
  - ownership entries point at files that exist
  - parallel markdown twins of a contract (docs/architecture.md, ...)
  - acceptance criteria <-> covers("AC-...") markers in tests/, both directions
  - operationIds parked in x-planned-operations that also appear under paths

Deliberately dependency-free: it scans the YAML line by line instead of importing
PyYAML, so it runs in any CI image. That means it is a lint, not a parser — it
flags shapes, and `tests/test_spec.py` still does the semantic guarding.

Output: one finding per line as `file:line:severity:message`.
Exit code: 0 clean, 1 findings, 2 usage/IO error.

Usage:
    python3 contract_audit.py /path/to/repo
    python3 contract_audit.py . --format text
    python3 contract_audit.py . --severity HIGH     # only hard failures
"""
import argparse
import re
import sys
from pathlib import Path

CONTRACT_DIR = "contracts"
REQUIRED_FILES = ("business-spec.yaml", "openapi.yaml", "architecture.yaml")

REQUIRED_SECTIONS = {
    "business-spec.yaml": ("meta",),
    "architecture.yaml": ("meta",),
    "openapi.yaml": ("openapi", "info", "paths"),
}
# Sections the pattern expects but an existing repo may legitimately name differently
# (the origin repo keeps its permission matrix under `rbac`, its AC in architecture.yaml).
RECOMMENDED_SECTIONS = {
    "business-spec.yaml": ("actors", "flows", "acceptance_criteria", "out_of_scope"),
    "architecture.yaml": ("principles", "ownership", "blockers", "decisions"),
    "openapi.yaml": ("components", "servers"),
}

SCHEMA_LINE = re.compile(r"^#\s*yaml-language-server:\s*\$schema=")
# Values YAML 1.1 turns into booleans behind your back. PyYAML resolves the long
# forms; single y/n are only booleans in other 1.1 parsers, so they rank lower.
IMPLICIT_BOOL = re.compile(r"^(yes|Yes|YES|no|No|NO|on|On|ON|off|Off|OFF)$")
IMPLICIT_BOOL_WEAK = re.compile(r"^[yYnN]$")
# "1.10" reads as the float 1.1, silently dropping the trailing zero. Two or more
# decimals ending in 0 is the tell; `minimum: 2000.0` is an honest float, not a version.
VERSIONY_FLOAT = re.compile(r"^\d+\.\d+0$")
VERSION_KEY = re.compile(r"version", re.I)
BARE_NUMBER = re.compile(r"^\d+(\.\d+)?$")
BARE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Any mapping line, including OpenAPI path keys (`/api/x:`), quoted keys (`"200":`),
# extension keys (`x-planned-operations:`) and scaffold placeholders (`<Resource>:`).
# A key may not START with a quote unless it is fully quoted — otherwise a prose
# sequence item such as `- "Curated only: keep publishing"` reads as a mapping.
KEY_LINE = re.compile(
    r"^(?P<indent>\s*)(?P<dash>-\s+)?"
    r"(?P<key>\"[^\"]+\"|'[^']+'|[^\s#:\"'][^:]*?)\s*:(?P<rest>\s.*|)$"
)
# Values that mean "no reference", not the literal string.
NULLISH = {"", "null", "~", "None"}
AC_ID = re.compile(r"\bAC-[A-Z0-9]+-\d+\b")
# Both marker styles seen in practice: a `# covers(AC-X-01)` comment above a test,
# and a `covers("AC-X-01")` decorator/helper call.
COVERS = re.compile(r"covers\(\s*[\"']?(AC-[A-Z0-9]+-\d+)[\"']?\s*\)")

MD_TWINS = ("architecture.md", "business-spec.md", "openapi.md", "business_spec.md")


class Finding:
    def __init__(self, path, line, severity, message):
        self.path, self.line, self.severity, self.message = path, line, severity, message

    def __str__(self):
        return f"{self.path}:{self.line}:{self.severity}:{self.message}"


def _lines(path):
    return path.read_text(encoding="utf-8").splitlines()


# ---- line-oriented YAML scan ------------------------------------------------
def scan_mapping(lines):
    """Yield (lineno, indent, key, value, in_list_item) for every mapping line.

    Block scalars (| and >) and quoted multi-line values are skipped so their
    contents are not mistaken for keys.
    """
    skip_until_indent = None
    for i, raw in enumerate(lines, start=1):
        if skip_until_indent is not None:
            if raw.strip() == "" or (len(raw) - len(raw.lstrip())) > skip_until_indent:
                continue
            skip_until_indent = None
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = KEY_LINE.match(raw)
        if not m:
            continue
        indent = len(m.group("indent")) + (len(m.group("dash")) if m.group("dash") else 0)
        value = m.group("rest").strip()
        if value.startswith(("|", ">")):
            skip_until_indent = len(m.group("indent"))
        yield i, indent, m.group("key"), value, bool(m.group("dash"))


def check_duplicate_keys(rel, lines):
    """Flag a key repeated inside the same mapping.

    Scopes are tracked by indent; a `- ` item opens a fresh scope at its indent
    so two list entries may legitimately share key names.
    """
    findings = []
    stack = []  # list of [indent, seen_keys]
    for lineno, indent, key, _value, in_list in scan_mapping(lines):
        while stack and stack[-1][0] > indent:
            stack.pop()
        if in_list:
            while stack and stack[-1][0] >= indent:
                stack.pop()
            stack.append([indent, set()])
        if not stack or stack[-1][0] < indent:
            stack.append([indent, set()])
        seen = stack[-1][1]
        if key in seen:
            findings.append(Finding(rel, lineno, "HIGH",
                                    f"duplicate key '{key}' in the same mapping — "
                                    "a YAML parser keeps only the last one"))
        seen.add(key)
    return findings


def check_implicit_typing(rel, lines):
    findings = []
    for lineno, _indent, key, value, _in_list in scan_mapping(lines):
        if not value or value.startswith("#"):
            continue
        bare = value.split(" #")[0].strip()
        if IMPLICIT_BOOL.match(bare):
            findings.append(Finding(rel, lineno, "HIGH",
                                    f"'{key}: {bare}' — YAML 1.1 reads this as a boolean; quote it"))
        elif IMPLICIT_BOOL_WEAK.match(bare):
            findings.append(Finding(rel, lineno, "MED",
                                    f"'{key}: {bare}' stays a string in PyYAML but becomes a boolean "
                                    "in other YAML 1.1 parsers; quote it"))
        elif VERSIONY_FLOAT.match(bare):
            findings.append(Finding(rel, lineno, "HIGH",
                                    f"'{key}: {bare}' parses as the float {float(bare)}, losing the "
                                    "trailing zero; quote it"))
        elif VERSION_KEY.search(key) and BARE_NUMBER.match(bare):
            findings.append(Finding(rel, lineno, "MED",
                                    f"'{key}: {bare}' is a number, not a version string; quote it"))
        elif BARE_DATE.match(bare):
            findings.append(Finding(rel, lineno, "LOW",
                                    f"'{key}: {bare}' parses as a date object; quote it for stable comparisons"))
    return findings


def check_tabs(rel, lines):
    return [Finding(rel, i, "HIGH", "tab character in indentation — YAML forbids tabs")
            for i, raw in enumerate(lines, start=1) if raw[:len(raw) - len(raw.lstrip())].count("\t")]


def top_level_keys(lines):
    return {key for _l, indent, key, _v, in_list in scan_mapping(lines) if indent == 0 and not in_list}


# ---- ADR / ownership / blockers --------------------------------------------
def parse_list_records(lines, section):
    """Collect the records of a top-level list section as {key: (lineno, value)} dicts.

    A new record starts only at the section's own item indent, so a nested list
    inside a record (options, affects, steps) does not split it in two.
    """
    records, current, in_section, base_indent = [], None, False, None
    for lineno, indent, key, value, in_list in scan_mapping(lines):
        if indent == 0 and not in_list:
            if key == section:
                in_section, current = True, None
                continue
            if in_section:
                break
        if not in_section:
            continue
        if in_list and (base_indent is None or indent == base_indent):
            if current:
                records.append(current)
            current, base_indent = {}, indent
        if current is not None and indent >= base_indent:
            current.setdefault(key, (lineno, value))
    if current:
        records.append(current)
    return records


def check_adrs(rel, lines, repo):
    findings = []
    blockers = {v.strip().strip("\"'") for r in parse_list_records(lines, "blockers")
                for k, (_l, v) in r.items() if k == "id"}
    for rec in parse_list_records(lines, "decisions"):
        lineno = min(l for l, _v in rec.values())
        adr_id = rec.get("id", (lineno, "?"))[1] or "?"
        status = (rec.get("status", (lineno, ""))[1] or "").split("#")[0].strip()
        if status == "decided":
            for field in ("date", "rationale"):
                if field not in rec:
                    findings.append(Finding(rel, lineno, "HIGH",
                                            f"{adr_id}: status decided but no '{field}'"))
        elif status == "open":
            for field in ("resolution_criteria", "default_if_unresolved"):
                if field not in rec:
                    findings.append(Finding(rel, lineno, "HIGH",
                                            f"{adr_id}: status open but no '{field}' — "
                                            "an agent will guess instead of waiting"))
            for target in _inline_list(rec.get("affects", (lineno, ""))[1]):
                if (repo / target).exists():
                    findings.append(Finding(rel, lineno, "HIGH",
                                            f"{adr_id} is open but '{target}' already exists — "
                                            "code was written before the decision"))
        elif status not in ("superseded", ""):
            findings.append(Finding(rel, lineno, "MED",
                                    f"{adr_id}: unknown status '{status}' "
                                    "(expected open|decided|superseded)"))
        if "blocked_by" in rec:
            ref = rec["blocked_by"][1].split("#")[0].strip().strip("\"'")
            if ref not in NULLISH and blockers and ref not in blockers:
                findings.append(Finding(rel, rec["blocked_by"][0], "MED",
                                        f"{adr_id}: blocked_by '{ref}' is not a declared blocker id"))
    return findings


def _inline_list(value):
    value = (value or "").strip()
    if not value.startswith("["):
        return []
    return [v.strip().strip("\"'") for v in value.strip("[]").split(",") if v.strip()]


def check_ownership(rel, lines, repo):
    findings = []
    for rec in parse_list_records(lines, "ownership"):
        if "file" not in rec:
            continue
        lineno, value = rec["file"]
        target = value.split("#")[0].strip().strip("\"'")
        if not target or any(ch in target for ch in "*?"):
            continue
        if not (repo / target).exists():
            findings.append(Finding(rel, lineno, "MED",
                                    f"ownership points at '{target}', which does not exist"))
        if "owner" not in rec:
            findings.append(Finding(rel, lineno, "HIGH", f"'{target}' has no owner"))
    return findings


def check_planned_operations(rel, lines):
    """An operationId parked in x-planned-operations must not also live under paths."""
    findings, section, planned, live = None, None, {}, {}
    findings = []
    for lineno, indent, key, value, _in_list in scan_mapping(lines):
        if indent == 0:
            section = key
            continue
        if key == "operationId" and section in ("paths", "x-planned-operations"):
            op = value.split("#")[0].strip().strip("\"'")
            (live if section == "paths" else planned)[op] = lineno
    for op, lineno in planned.items():
        if op in live:
            findings.append(Finding(rel, lineno, "HIGH",
                                    f"operationId '{op}' is both planned and live — "
                                    "move the block out of x-planned-operations"))
    return findings


# ---- cross-file -------------------------------------------------------------
def collect_acceptance_criteria(rel, lines):
    """AC may live in business-spec.yaml or architecture.yaml — collect from either."""
    declared = {}
    for rec in parse_list_records(lines, "acceptance_criteria"):
        if "id" in rec:
            lineno, value = rec["id"]
            match = AC_ID.search(value)
            if match:
                declared[match.group(0)] = (rel, lineno)
    return declared


def check_acceptance_criteria(declared, repo):
    """Bidirectional: every AC has a covers() marker; every marker names a real AC."""
    findings = []
    covered = set()
    tests_dir = repo / "tests"
    if tests_dir.is_dir():
        for path in tests_dir.rglob("*.py"):
            covered |= set(COVERS.findall(path.read_text(encoding="utf-8", errors="replace")))
    for ac, (rel, lineno) in declared.items():
        if ac not in covered:
            findings.append(Finding(rel, lineno, "MED",
                                    f"{ac} has no covers() marker in tests/ — untested criterion"))
    for ac in sorted(covered - set(declared)):
        findings.append(Finding("tests/", 0, "MED",
                                f"covers('{ac}') refers to an acceptance criterion that does not exist"))
    return findings


def check_md_twins(repo):
    findings = []
    for folder in (repo, repo / "docs", repo / CONTRACT_DIR):
        if not folder.is_dir():
            continue
        for name in MD_TWINS:
            twin = folder / name
            if twin.exists():
                findings.append(Finding(str(twin.relative_to(repo)), 1, "MED",
                                        "markdown twin of a contract file — one SSOT only; "
                                        "delete it (git history keeps it)"))
    return findings


def audit(repo):
    findings, acceptance = [], {}
    cdir = repo / CONTRACT_DIR
    if not cdir.is_dir():
        return [Finding(CONTRACT_DIR + "/", 0, "HIGH",
                        "no contracts/ directory — run scaffold_contracts.py first")]
    for name in REQUIRED_FILES:
        if not (cdir / name).exists():
            findings.append(Finding(f"{CONTRACT_DIR}/{name}", 0, "HIGH", "missing contract file"))
    if not (cdir / "schemas").is_dir():
        findings.append(Finding(f"{CONTRACT_DIR}/schemas/", 0, "MED",
                                "no schemas/ directory — spec files have no meta-schema"))

    for path in sorted(cdir.glob("*.yaml")):
        rel = str(path.relative_to(repo))
        lines = _lines(path)
        if not lines:
            findings.append(Finding(rel, 0, "HIGH", "empty contract file"))
            continue
        if path.name != "openapi.yaml":
            if not SCHEMA_LINE.match(lines[0]):
                findings.append(Finding(rel, 1, "MED",
                                        "first line is not '# yaml-language-server: $schema=...' — "
                                        "the IDE cannot validate while typing"))
            schema = cdir / "schemas" / f"{path.stem}.schema.json"
            if not schema.exists():
                findings.append(Finding(rel, 1, "MED", f"no meta-schema at schemas/{schema.name}"))
        findings += check_tabs(rel, lines)
        findings += check_duplicate_keys(rel, lines)
        findings += check_implicit_typing(rel, lines)
        present = top_level_keys(lines)
        for section in REQUIRED_SECTIONS.get(path.name, ()):
            if section not in present:
                findings.append(Finding(rel, 1, "HIGH", f"missing required top-level section '{section}'"))
        for section in RECOMMENDED_SECTIONS.get(path.name, ()):
            if section not in present:
                findings.append(Finding(rel, 1, "LOW",
                                        f"no '{section}' section — the pattern expects one "
                                        "(fine if this repo names it differently)"))
        if path.name == "architecture.yaml":
            findings += check_adrs(rel, lines, repo)
            findings += check_ownership(rel, lines, repo)
        if path.name == "openapi.yaml":
            findings += check_planned_operations(rel, lines)
        acceptance.update(collect_acceptance_criteria(rel, lines))

    findings += check_acceptance_criteria(acceptance, repo)
    findings += check_md_twins(repo)
    if not (repo / "tests").is_dir():
        findings.append(Finding("tests/", 0, "HIGH",
                                "no tests/ directory — a spec without guards will rot"))
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repo", nargs="?", default=".", help="repo root (default: .)")
    parser.add_argument("--format", choices=("line", "text"), default="line",
                        help="line = file:line:severity:message (CI), text = grouped (human)")
    parser.add_argument("--severity", choices=("HIGH", "MED", "LOW"), default="LOW",
                        help="minimum severity to report (default: LOW = everything)")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"error: {repo} is not a directory", file=sys.stderr)
        return 2
    try:
        findings = audit(repo)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    order = {"HIGH": 0, "MED": 1, "LOW": 2}
    findings = [f for f in findings if order[f.severity] <= order[args.severity]]
    findings.sort(key=lambda f: (order[f.severity], f.path, f.line))

    if args.format == "line":
        for f in findings:
            print(f)
    else:
        if not findings:
            print(f"contract bundle clean: {repo}")
        else:
            print(f"{len(findings)} finding(s) in {repo}\n")
            current = None
            for f in findings:
                if f.path != current:
                    current = f.path
                    print(f"  {current}")
                where = f"line {f.line}" if f.line else "-"
                print(f"    [{f.severity}] {where}: {f.message}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
