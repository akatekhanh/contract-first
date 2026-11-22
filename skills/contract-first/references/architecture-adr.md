# `contracts/architecture.yaml` — layers, ownership, decisions

## Shape

```yaml
# yaml-language-server: $schema=./schemas/architecture.schema.json
meta: { name, version, style, deployment, related_artifacts }
principles:        # - { id, rule }  e.g. dependency rule, contract-first, validation-at-the-edge
ownership:         # - { file, owner, role }   ← exactly ONE owner per file
domain_model:
persistence:       # tables we own vs. read-only, concurrency strategy, grants still needed
runtime:           # diagram (block scalar) + how to run locally
deploy:            # policy, paths (who may deploy, preconditions, steps), agent_may_deploy: false
commands:          # test / lint / build — copy-pasteable
config:            # env var → source (config file / secret manager), kill switches
blockers:          # - { id, severity, detail }   ← waiting on someone outside
decisions:         # ADRs — see below
rollout:           # phase_1 / phase_2 / phase_3 when shipping in waves
```

`commands` and `config` are the sections agents read most: one gives them the exact test command, the other stops them inventing env var names.

## Decision vs. spike vs. blocker

Three things that get conflated. Separated, each has its own way to close:

| Concept | What it is | Who clears it | Where it lives |
|---|---|---|---|
| blocker | waiting on the outside (network access, a grant, an approval) | someone else | contract |
| ADR | a design choice + its reasoning; `open` or `decided` | you | contract |
| spike | timeboxed investigation that produces evidence | you | **tracker**, not the contract |

## ADR format

```yaml
decisions:
  - id: ADR-001
    title: <the decision>
    status: decided                 # open | decided | superseded
    date: "YYYY-MM-DD"
    choice: <what was chosen>
    rationale: <why>
    alternatives_rejected: [<option + why it lost>]
    consequences: [<what you gain, what you pay>]
    affects: [<files this touches>]

  - id: ADR-002
    title: <still undecided>
    status: open
    options: [<A>, <B>]
    resolution_criteria: <what evidence will settle it>   # = the spike's exit criteria
    blocked_by: <blocker id>
    default_if_unresolved: <what an agent must do meanwhile>
    affects: [<files not yet written>]
```

The three fields on an `open` ADR carry most of the value:

- `resolution_criteria` separates a real decision from a lingering worry.
- `default_if_unresolved` keeps agents from guessing while you wait.
- `affects` scopes exactly what is blocked, so everything else keeps moving.

**Guard it**: while an ADR is `open`, no file in its `affects` list may exist. That is "decide first, code second" expressed as a test rather than a hope.

## When an ADR is worth writing

Only if one of these is true: hard to reverse (changing it later costs a sprint or a data migration) · it crosses several layers or owners · someone will ask "why is this like this?" in three months. Otherwise: pick, leave a one-line comment, move on.

Keep ADRs in `architecture.yaml` up to roughly 20 records, then split them into their own file. Deciding the threshold now avoids arguing about it later.

## Deploy

Declare it in `architecture.yaml#deploy`: `policy`, `paths` (each path states who may deploy, the preconditions, the steps, and the follow-up work), and `agent_may_deploy: false`.

For multi-step deploys add `contracts/deploy-plan.yaml` — a data-driven runbook where each step has `id / name / owner / kind (read-only|write|manual) / command / expect / on_fail`. Guards to pin: a step with `owner: agent` must have `kind: read-only`, and every `write` step must have `on_fail` or `rollback`.
