# Contract First — Specs That Bite Back

> **A multi-provider, multi-model AI agent skill that scaffolds machine-checkable YAML contracts, file ownership boundaries, and spec↔code guard tests so coding agents never drift.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3 Stdlib Only](https://img.shields.io/badge/Scripts-Python%203%20Stdlib%20Only-green.svg)](skills/contract-first/scripts/)
[![Multi-Provider](https://img.shields.io/badge/Providers-Antigravity%20%7C%20Claude%20Code%20%7C%20Codex%20%7C%20Cursor%20%7C%20Gemini%20CLI%20%7C%20OpenCode-purple.svg)](#installation)

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

## Installation

Structured for native discovery across every major AI coding harness (inspired by [`obra/superpowers`](https://github.com/obra/superpowers)):

### Universal (`npx skills`)

```bash
npx skills add akatekhanh/contract-first
```

### Antigravity (`agy`)

```bash
agy plugin install https://github.com/akatekhanh/contract-first
```
*(Uses `.antigravity-plugin/plugin.json` and ingests `skills/contract-first/` automatically.)*

### Claude Code

Inside Claude Code:
```text
/plugin marketplace add akatekhanh/contract-first
/plugin install contract-first@contract-first-dev
```
*(Uses `.claude-plugin/marketplace.json` + `.claude-plugin/plugin.json`.)*

### OpenAI Codex CLI / App

```bash
# Via universal .agents/plugins marketplace or direct skill clone:
git clone https://github.com/akatekhanh/contract-first.git /tmp/contract-first \
  && cp -R /tmp/contract-first/skills/contract-first ~/.codex/skills/contract-first \
  && rm -rf /tmp/contract-first
```
*(Includes `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json`.)*

### Cursor

Install from repository URL using `.cursor-plugin/plugin.json` (`"skills": "./skills/"`), or clone `skills/contract-first` into `.cursor/skills/`.

### Gemini CLI

```bash
gemini extensions install https://github.com/akatekhanh/contract-first
```
*(Uses `gemini-extension.json` + `GEMINI.md`.)*

### OpenCode / Hermes / Other Harnesses

Point your harness at `AGENTS.md` or copy `skills/contract-first/` into your shared `~/.agents/skills/` directory:

```bash
git clone https://github.com/akatekhanh/contract-first.git /tmp/contract-first \
  && mkdir -p ~/.agents/skills \
  && cp -R /tmp/contract-first/skills/contract-first ~/.agents/skills/contract-first \
  && rm -rf /tmp/contract-first
```

Once installed, trigger it naturally in any session:
- *"Set up contract-first for this repo"*
- *"Scaffold the contracts before we start coding"*
- *"Audit this repo with contract-first and find spec↔code drift"*

---

## What Gets Scaffolded in Your Project

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

## Multi-Agent & Multi-Model Fan-Out

The `ownership` table in `contracts/architecture.yaml` acts as a second contract when fanning work out across parallel agents or mixed model families:

| Role | Owns | Recommended Model Tier | Examples (Multi-Provider) |
|---|---|---|---|
| `ARCHITECT` | `contracts/`, entities, ports/interfaces, shared signatures | Frontier / high-reasoning | Claude Opus · Gemini Pro / Neon · GPT-5 (high) |
| `AGENT-DOMAIN` / `ADAPTER` / `API` / `FE` | One implementation layer inside owned files | Mid / balanced | Claude Sonnet · Gemini Pro · GPT-5 / Codex |
| `RESEARCH` | Read-only lookup & repo exploration | Fast / lightweight | Claude Haiku · Gemini Flash · GPT-5 mini |
| `REVIEWER` | Diff vs. contract verification | **Separate agent / cross-model** | Pair different families (e.g., Gemini writes, Claude reviews) |

See [`skills/contract-first/references/multi-agent-ownership.md`](skills/contract-first/references/multi-agent-ownership.md) for the full sequencing protocol.

---

## CLI Scripts (Zero External Dependencies)

Both helper scripts use **Python 3 standard library only** and are CI-ready (`exit 0` clean, `exit 1` findings/skipped, `exit 2` error).

### 1. Scaffold a new contract bundle

```bash
python3 skills/contract-first/scripts/scaffold_contracts.py /path/to/repo --name "My App" --date 2026-11-22
# Preview without writing:
python3 skills/contract-first/scripts/scaffold_contracts.py /path/to/repo --name "My App" --dry-run
```

### 2. Audit an existing repo for contract defects

```bash
python3 skills/contract-first/scripts/contract_audit.py /path/to/repo --format text
# CI mode (file:line:severity:message, hard failures only):
python3 skills/contract-first/scripts/contract_audit.py /path/to/repo --severity HIGH
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

## Repository Structure

```text
contract-first/
├── .antigravity-plugin/plugin.json    # Antigravity (agy) native plugin
├── .claude-plugin/                    # Claude Code plugin + marketplace
├── .codex-plugin/plugin.json          # Codex CLI / App plugin
├── .cursor-plugin/plugin.json         # Cursor plugin
├── .agents/plugins/marketplace.json   # Universal .agents marketplace
├── gemini-extension.json + GEMINI.md  # Gemini CLI extension
├── AGENTS.md                          # Universal agent entry point
├── skills/contract-first/
│   ├── SKILL.md                       # Core skill instructions
│   ├── references/                    # Progressive-disclosure deep guides
│   └── scripts/                       # Zero-dependency scaffold + audit CLIs
├── tests/test_skill_layout.py         # Manifest sync, layout & script smoke tests
└── .github/workflows/ci.yml           # Automated CI verification
```

---

## License

[MIT](LICENSE)
