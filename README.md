# Contract First — Specs That Bite Back

> **An AI coding agent skill that scaffolds machine-checkable YAML contracts, file ownership boundaries, and spec↔code guard tests so multi-agent codebases never drift.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3 Stdlib Only](https://img.shields.io/badge/Scripts-Python%203%20Stdlib%20Only-green.svg)](scripts/)
[![Works with](https://img.shields.io/badge/Works%20with-Claude%20Code%20%7C%20Antigravity%20%7C%20Codex%20%7C%20Cursor-purple.svg)](#install)

---

## Why This Exists

When most of your code is written by AI agents, a constraint that lives only in your head—or in a paragraph an agent is *supposed* to remember—**is not a constraint**.

- Prose rules burn context and silently rot.
- Parallel agents without file boundaries negotiate interfaces *through* your codebase and leave four half-compatible versions of the same idea.
- Open design decisions turn into bare `TODO`s that agents treat as permission to invent.

**Contract First** turns your spec into **executable data**—three YAML contracts, JSON Schemas, a file-ownership boundary table, and automated guard tests—before the first line of implementation code is written.

---

## The Five Rules

1. **If a rule can't be tested, don't write it as a rule.** Important enough to keep → make it a test.
2. **A matrix is DATA, not a Markdown table.** Only then can tests compare it against real enums and route guards in code.
3. **One SSOT.** Never keep a parallel `.md` copy of a YAML contract.
4. **Order: Spec → Contract → Code.** Domain decides the API; API decides the layers. Unbuilt endpoints live under `x-planned-operations`.
5. **An agent that finds the contract wrong REPORTS it — it does not edit it.** Otherwise the contract becomes a scratchpad.

---

## Install

### Quick install (recommended)

```bash
npx skills add akatekhanh/contract-first
```

### Manual install (Antigravity `agy` / Claude Code / Codex / Cursor)

```bash
# Global shared skills directory (~/.agents/skills)
git clone https://github.com/akatekhanh/contract-first.git ~/.agents/skills/contract-first

# Or for Claude Code specifically
git clone https://github.com/akatekhanh/contract-first.git ~/.claude/skills/contract-first
```

Once installed, trigger it naturally in any coding agent session:
- *"Set up contract-first for this repo"*
- *"Scaffold the contracts before we start coding"*
- *"Audit this repo with contract-first and find spec↔code drift"*

---

## What Gets Scaffolded

```text
<your-repo>/
├── contracts/
│   ├── business-spec.yaml             # 1. Domain: actors, state machine, flows, copy, AC
│   ├── openapi.yaml                   # 2. API + entity model (OpenAPI 3.1 + x-planned-operations)
│   ├── architecture.yaml              # 3. Layers, file ownership, persistence, ADRs, blockers
│   └── schemas/
│       ├── business-spec.schema.json  # JSON Schema Draft 2020-12
│       └── architecture.schema.json   # JSON Schema Draft 2020-12
├── tests/
│   └── test_spec.py                   # Strict YAML loader + schema + orphan-enum + ADR + AC guards
└── AGENTS.md                          # Short pointer to contracts/, never restates them
```

---

## CLI Scripts (Zero External Dependencies)

Both helper scripts use **Python 3 standard library only** and are CI-ready (`exit 0` clean, `exit 1` findings/skipped, `exit 2` error).

### 1. Scaffold a new contract bundle

```bash
python3 scripts/scaffold_contracts.py /path/to/repo --name "My App" --date 2026-11-22
# Preview without writing:
python3 scripts/scaffold_contracts.py /path/to/repo --name "My App" --dry-run
```

### 2. Audit an existing repo for contract defects

```bash
python3 scripts/contract_audit.py /path/to/repo --format text
# CI mode (file:line:severity:message, hard failures only):
python3 scripts/contract_audit.py /path/to/repo --severity HIGH
```

What `contract_audit.py` catches automatically:
- Missing contract files or meta-schemas (`schemas/*.schema.json`)
- Missing `# yaml-language-server: $schema=...` header lines
- Duplicate YAML mapping keys (which parsers silently overwrite)
- YAML 1.1 implicit-typing traps (`YES`/`NO`/`ON`/`OFF`, version floats like `1.10`, bare dates) and tab indentation
- Broken ADR invariants (decided ADRs missing `date`/`rationale`; open ADRs missing `resolution_criteria`/`default_if_unresolved`, or files in `affects` written before the decision was made)
- Dangling `blocked_by` references or `ownership` entries pointing to nonexistent files
- Duplicate `operationId`s parked in both `paths` and `x-planned-operations`
- Bidirectional `AC-*` acceptance criteria ↔ `covers("AC-...")` test markers
- Parallel Markdown twins (`docs/architecture.md`, `business-spec.md`, etc.)

---

## Multi-Agent Fan-Out

The `ownership` table in `contracts/architecture.yaml` acts as a second contract when running parallel agents:

| Role | Owns | Must Not |
|---|---|---|
| `ARCHITECT` | `contracts/`, entities, ports/interfaces, shared signatures | — |
| `AGENT-DOMAIN` | Pure domain logic + unit tests | Import frameworks or change shared signatures |
| `AGENT-ADAPTER` | Port implementations, DDL/migrations | Touch domain or contracts |
| `AGENT-API` | Routes matching `openapi.yaml`, DI wiring | Add endpoints outside the contract |
| `AGENT-FE` | UI + generated types from OpenAPI | Invent strings outside `business-spec.yaml#copy` |

---

## Deep-Dive References

Progressive disclosure keeps agent context lean—detailed guides live in [`references/`](references/):

- [`references/business-spec.md`](references/business-spec.md) — Actors, identity, state machines, flows, SLA, errors, shared copy, selective acceptance criteria
- [`references/openapi-contract.md`](references/openapi-contract.md) — OpenAPI 3.1 rules, discriminator mappings, Problem shape, `x-planned-operations`
- [`references/architecture-adr.md`](references/architecture-adr.md) — `architecture.yaml`, ADR vs. blocker vs. spike, `deploy-plan.yaml`
- [`references/enforcement-tests.md`](references/enforcement-tests.md) — Strict YAML loader, implicit-typing traps, AC markers, guard verification
- [`references/multi-agent-ownership.md`](references/multi-agent-ownership.md) — Role boundaries, model-tier routing, parallel feature sequencing

---

## License

[MIT](LICENSE)
