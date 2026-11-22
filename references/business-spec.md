# `contracts/business-spec.yaml` — the domain contract

The first file written and the one code copies its words from. It answers: who acts, what states exist, what the user is told, and what is deliberately not built.

## Shape

```yaml
# yaml-language-server: $schema=./schemas/business-spec.schema.json
meta:
  name: <project>
  version: "1.0"
  updated: "YYYY-MM-DD"
  purpose: <one sentence>
  related_artifacts: [./openapi.yaml, ./architecture.yaml]

actors:                  # - { role, who | who_env, can: [...] }
identity:                # where identity comes from, SSOT for membership, dev fallback
state_machine:
  initial: <state>
  terminal: [<state>, ...]
  invariants: [<statement>, ...]
  transitions:           # - { action, role, role_constraint?, from, to, sets: [...] }
flows:                   # per flow: steps + the user-facing message VERBATIM
sla:                     # clock, policy per level, states, known_behaviour
errors:                  # - { http, when, message (verbatim), fe_behaviour }
validation_rules:
idempotency:
copy:                    # labels/messages used by BOTH backend and frontend
acceptance_criteria:     # - { id: AC-XXX-01, text, ref }
out_of_scope:            # what is explicitly NOT built
```

## Rules that matter

**Permission matrix as data.** If there is a matrix, spell out every subject: what it receives, what it can read, what it can modify. As YAML rows — a markdown table cannot be compared against `app.routes` or a DB CHECK constraint by a test.

**Messages verbatim.** Every user-facing string appears here in full, and code copies it. This is what makes `copy` testable: the guard asserts the backend's message string and the frontend's label both equal the spec value. A paraphrase in code is a failing test, not a style preference.

**`state_machine.transitions` is the authority.** Each row names the action, the role allowed to perform it, the from/to states and the fields it sets. Tests then check: no transition uses a state/action/role outside the enums, and the (role, from, action) triple matches what the domain code actually permits.

**SLA as policy data, not prose.** `sla.policy` maps a level to a duration; the guard compares those numbers to the SLA constants in code. `known_behaviour` is where you record the deliberate imperfection ("timer keeps running while the job is paused") so nobody files it as a bug or silently "fixes" it.

**`errors` is a three-column contract**: HTTP status, the condition, the exact message, plus what the frontend does with it (toast, inline field, redirect). This is the file the API and the UI agree on without talking to each other.

**`out_of_scope` earns its place.** Agents fill silence with invention. An explicit "no bulk import in v1" costs one line and prevents a day of unrequested code.

## Acceptance criteria

```yaml
acceptance_criteria:
  - id: AC-PERM-01
    text: A viewer cannot transition a job to approved.
    ref: state_machine.transitions
```

Aim for roughly ten, on behaviour where being wrong breaks the business or the permission model. Each one gets a `covers("AC-PERM-01")` marker in a test, checked both ways: an AC with no test fails, a marker pointing at a nonexistent AC fails. That bidirectional check is the whole value — one-directional tracing rots quietly.

## Writing order discipline

This file must be technology-free. The moment you write "Kafka", "SMTP", "Delta table", you have jumped into `architecture.yaml`. Names of external systems are allowed only where they are part of the domain reality (e.g. "the bank's core system returns the balance"), not as an implementation choice.
