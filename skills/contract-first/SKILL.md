---
name: contract-first
description: Scaffold and enforce a machine-checkable contract bundle — contracts/{business-spec,openapi,architecture}.yaml plus spec↔code tests. Use when starting a new project/repo/app, when the user says "contract-first", "set up the contracts", "spec first", "scaffold the project pattern", when deciding how AI agents should share a codebase without drifting, or when auditing an existing repo for missing/stale specs (including migrating docs/*.md architecture notes into contracts/*.yaml). Covers ADR vs blocker vs spike, ownership tables for multi-agent fan-out, and the guard tests that keep the contract honest.
---

# Contract First

Every project gets its contract bundle before it gets code. The contract is the SSOT: backend entities, frontend types and tests all mirror it — never the reverse.

The reason this pattern exists: when most of the code is written by AI agents, a constraint that lives only in someone's head, or in a paragraph an agent is supposed to remember, is not a constraint. It has to be in a machine-readable file, and a test has to watch it.

## When to use

- New repo/app/service — before the first line of implementation code.
- "Set up contracts / spec-first / the project pattern" or `/contract-first`.
- Before fanning work out to several agents (the ownership table is what keeps them from overwriting each other).
- **Audit mode**: an existing repo — find what drifted between code and spec, or migrate prose `docs/*.md` designs into `contracts/*.yaml`.

## Foundations

1. **If a rule can't be tested, don't write it as a rule.** Prose rules burn context, get skipped anyway, and nobody learns when they're violated. Important enough to keep → turn it into a test. Not important enough for a test → not important enough to make people remember.
2. **A matrix is DATA, not a markdown table.** Only then can a test compare it against the enums and constants in the code.
3. **One SSOT.** Never keep a parallel `.md` copy of a YAML contract.
4. **Order: spec → contract → code.** Unbuilt features still get a spec and a schema; operations without a route yet live under `x-planned-operations`.
5. **Selective traceability.** Attach acceptance criteria only to behaviour whose failure breaks the business or the permission model (~10 AC for one app). Tracing everything is ceremony.

## The bundle

```
<repo>/
  contracts/
    business-spec.yaml           # 1. domain: actors, state machine, flows, copy, AC
    openapi.yaml                 # 2. API + entity model (OpenAPI 3.1)
    architecture.yaml            # 3. layers, ownership, persistence, ADRs, blockers
    deploy-plan.yaml             # (optional) step-by-step deploy runbook as data
    schemas/*.schema.json        # meta-schema per YAML file above
  tests/
    test_contract.py             # API contract ↔ code
    test_spec.py                 # spec ↔ code: structure, copy, AC, ADR, ownership
  AGENTS.md                      # short — points at contracts/, never restates them
```

Write them in that order: the domain decides the API, the API decides the layers. Warning sign that you skipped a step: you're writing `business-spec.yaml` and typing technology names (SMTP, Kafka, Delta).

Add a fourth contract file only when **both** hold: (a) it removes a duplication that actually exists, (b) it ships with a test. Copy and labels go in `business-spec.yaml#copy` — never a separate file.

## Workflow

1. **Gather the inputs.** Project name, one-line purpose, actors and what each may do, the main flows, intended stack, whether it deploys. Ask if unknown — do not assume.
2. **Scaffold**: `python3 scripts/scaffold_contracts.py <repo> --name "<Project>"` writes the three YAML files, their JSON Schemas, and a starter `tests/test_spec.py`. It never overwrites without `--force`.
3. **Fill in real content.** Anything undecided becomes an ADR with `status: open` or an explicit `unresolved: <question>` — never a bare `TODO`, which agents read as an invitation to invent.
4. **Write the guards in the same pass** (`references/enforcement-tests.md`). A spec with no test is a spec that will rot. Then break one guard on purpose and restore it — a guard that has never gone red is a guard of unknown value.
5. **Wire CI**: backend tests + lint + type-generation drift gate (`gen:api && git diff --exit-code`) + `test_spec.py`.
6. **Only then let agents write code**, split by the `ownership` table (`references/multi-agent-ownership.md`).
7. **Audit any time**: `python3 scripts/contract_audit.py <repo>` — exit 0 clean, 1 findings.

## Non-negotiables

- **An agent that finds the contract wrong REPORTS it — it does not edit it.** If everyone may edit the contract, the contract is a scratchpad.
- **Every file has exactly one owner** in `architecture.yaml#ownership`. The boundary lives in the file, not in a prompt instruction.
- **No orphan enums.** Every status/action/role used in `business-spec.yaml` exists in an `openapi.yaml` enum, and vice versa.
- **User-facing strings live in `business-spec.yaml#copy`** and are copied into code — backend messages and frontend labels come from the same source.
- **An open ADR must not block the whole feature.** Guard it: while an ADR is `open`, every file in its `affects` list must not exist yet.
- **`agent_may_deploy: false`.** Agents run validation and read-only steps; deploying is for a pipeline or a human.

## Scripts

| Script | Use |
|---|---|
| `scripts/scaffold_contracts.py <repo> --name X` | Create the bundle: 3 YAML contracts + `schemas/*.schema.json` + starter `tests/test_spec.py`. `--force` to overwrite, `--dry-run` to preview. |
| `scripts/contract_audit.py <repo>` | Audit an existing bundle: missing files, duplicate YAML keys, YAML-1.1 implicit-typing hazards, missing `yaml-language-server` line, ADR field rules, `ownership` paths that don't exist, parallel `.md` twins, AC ↔ `covers()` markers. Exit 1 on findings. |

Both are Python 3 stdlib only and CI-safe (`--help`, exit 0 = clean).

## References

- `references/business-spec.md` — the domain contract: actors, identity, state machine, flows, SLA, errors, copy, AC, out-of-scope.
- `references/openapi-contract.md` — OpenAPI 3.1 rules, discriminator mapping, Problem shape, `x-planned-operations`, two-way type enforcement.
- `references/architecture-adr.md` — `architecture.yaml` shape, ADR vs blocker vs spike, when an ADR is worth writing, `deploy-plan.yaml`.
- `references/enforcement-tests.md` — the guard tests, strict YAML loader, implicit-typing trap, AC markers, how to verify a guard.
- `references/multi-agent-ownership.md` — agent roles, ownership as a second contract, which model tier gets which job.

## Hand-offs

`solution-architect` produces the architecture that `architecture.yaml` records; `data-architect` owns the persistence section; `project-manager` tracks spikes and roadmap (spikes belong in the tracker, not the contract); `qa-automation` turns acceptance criteria into e2e coverage; `security-reviewer` checks the permission matrix against real route guards.

## Over-tightening — signs to stop

- Artifact count grows but no existing duplication got deleted.
- Traceability on every spec line instead of the load-bearing parts.
- A status field nobody has updated in six months (`outcome: null` forever).
- A new rule guarding a failure that has never happened.
- Copy split into its own file instead of `business-spec.yaml#copy`.

Set the threshold in advance to avoid arguing later: keep ADRs inside `architecture.yaml` until roughly 20 records, then split them out.

## Finishing checklist

- [ ] `contracts/` holds all three YAML files; no parallel `.md` version survives.
- [ ] `openapi.yaml` parses; no orphan enums in either direction against `business-spec.yaml`.
- [ ] Every spec YAML has a JSON Schema plus a `# yaml-language-server: $schema=…` first line.
- [ ] `architecture.yaml` has `principles`, `ownership`, `blockers`, `decisions`.
- [ ] ~10 AC on load-bearing behaviour, `covers()` markers checked in both directions.
- [ ] One guard was deliberately broken and went red in the right place.
- [ ] `AGENTS.md` is short and points at the contracts instead of retelling them.
- [ ] `contract_audit.py` exits 0.
