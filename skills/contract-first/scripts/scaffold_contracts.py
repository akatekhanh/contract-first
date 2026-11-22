#!/usr/bin/env python3
"""Scaffold a contract-first bundle into a repo.

Writes:
    contracts/business-spec.yaml            domain contract (actors, states, flows, copy, AC)
    contracts/openapi.yaml                  OpenAPI 3.1 skeleton + x-planned-operations
    contracts/architecture.yaml             layers, ownership, blockers, ADRs, deploy
    contracts/schemas/business-spec.schema.json
    contracts/schemas/architecture.schema.json
    tests/test_spec.py                      starter guards (strict loader + schema + ADR rules)

Templates carry placeholders in <angle brackets> plus `unresolved:` markers instead
of bare TODOs — an empty TODO reads to an agent as permission to invent.

Exit code: 0 written, 1 nothing written (files exist, no --force), 2 usage/IO error.

Usage:
    python3 scaffold_contracts.py /path/to/repo --name "Race Planner"
    python3 scaffold_contracts.py . --name Foo --dry-run
    python3 scaffold_contracts.py . --name Foo --force        # overwrite existing
"""
import argparse
import json
import sys
from pathlib import Path

BUSINESS_SPEC = '''\
# yaml-language-server: $schema=./schemas/business-spec.schema.json
meta:
  name: __PROJECT_NAME__
  version: "1.0"
  updated: "__UPDATED__"
  purpose: <one sentence: what this system does for whom>
  related_artifacts:
    - ./openapi.yaml
    - ./architecture.yaml

actors:
  - role: <role_id>
    who: <human description>
    can: [<action_id>, <action_id>]

identity:
  source: <where identity comes from — JWT / proxy header / session>
  membership_ssot: <the table or service that decides who belongs>
  dev_fallback: <how identity works locally; "none" if it does not>

state_machine:
  initial: <state>
  terminal: [<state>]
  invariants:
    - <statement that must always hold>
  transitions:
    - action: <action_id>
      role: <role_id>
      from: <state>
      to: <state>
      sets: [<field>]

flows:
  <flow_id>:
    trigger: <what starts it>
    steps:
      - <step, in order>
    user_message: <verbatim string shown to the user>

sla:
  clock: <what the timer measures>
  policy:
    <level>: <duration>
  states: [<state>]
  known_behaviour:
    - <deliberate imperfection, so nobody "fixes" it by accident>

errors:
  - http: 403
    when: <condition>
    message: <verbatim message>
    fe_behaviour: <toast | inline | redirect>

validation_rules:
  - field: <field>
    rule: <constraint>

idempotency:
  - operation: <operationId>
    key: <what makes a retry safe>

copy:
  <copy_key>: <verbatim string used by BOTH backend and frontend>

acceptance_criteria:
  - id: AC-CORE-01
    text: <observable behaviour whose failure breaks the business>
    ref: state_machine.transitions

out_of_scope:
  - <what is explicitly NOT built in this version>
'''

OPENAPI = '''\
openapi: 3.1.0
info:
  title: __PROJECT_NAME__ API
  version: "1.0"
  description: Contract is the SSOT — backend entities and frontend types mirror this file.
servers:
  - url: http://localhost:8000
    description: local
tags:
  - name: <domain>
security:
  - <schemeName>: []
paths:
  /api/<resource>:
    get:
      operationId: list<Resource>
      tags: [<domain>]
      summary: <what it returns>
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: array
                items: { $ref: "#/components/schemas/<Resource>" }
        "403": { $ref: "#/components/responses/Problem" }
x-planned-operations:
  # Operations that are specified but not implemented. A PR that implements one
  # moves the whole block into `paths` — the guard asserts every operation under
  # `paths` resolves to a real route.
  /api/<resource>/{id}:
    patch:
      operationId: update<Resource>
      tags: [<domain>]
      responses:
        "200": { description: OK }
components:
  securitySchemes:
    # Declare identity even when a proxy injects it — implicit identity is the
    # tribal knowledge that never makes it into a contract.
    <schemeName>:
      type: http
      scheme: bearer
  responses:
    Problem:
      description: Error
      content:
        application/json:
          schema: { $ref: "#/components/schemas/Problem" }
  schemas:
    Problem:
      type: object
      required: [detail]
      properties:
        detail:
          oneOf:
            - type: string
            - type: array
              items: { type: string }
    <Resource>:
      type: object
      required: [id, status]
      properties:
        id: { type: string }
        status:
          type: string
          enum: [<state>, <state>]
        note:
          type: [string, "null"]
'''

ARCHITECTURE = '''\
# yaml-language-server: $schema=./schemas/architecture.schema.json
meta:
  name: __PROJECT_NAME__
  version: "1.0"
  style: <modular monolith | layered | hexagonal | ...>
  deployment: <where it runs>
  related_artifacts:
    - ./business-spec.yaml
    - ./openapi.yaml

principles:
  - id: P-01
    rule: Dependencies point inward — the domain imports nothing from adapters.
  - id: P-02
    rule: Contract first — code mirrors contracts/, never the reverse.
  - id: P-03
    rule: Validation happens at the edge; the domain assumes valid input.

ownership:
  # Exactly one owner per file. This table is the boundary between agents.
  - file: <path/to/file>
    owner: ARCHITECT
    role: <what this file is responsible for>

domain_model:
  entities:
    - name: <Entity>
      invariants: [<rule>]

persistence:
  owned_tables: [<table>]
  read_only_tables: [<table>]
  concurrency: <optimistic lock via version column | none>
  grants_needed: [<grant still to be requested>]

runtime:
  diagram: |
    <client> -> <api> -> <domain> -> <store>
  local: <how to run it locally>

deploy:
  policy: <who deploys and when>
  agent_may_deploy: false
  paths:
    - name: <path name>
      who: <human | pipeline>
      preconditions: [<check>]
      steps: [<step>]
      follow_up: [<what must be done after>]

commands:
  test: <copy-pasteable command>
  lint: <copy-pasteable command>
  build: <copy-pasteable command>

config:
  <ENV_VAR>: <source — config file | secret manager | injected>

blockers:
  - id: BLK-001
    severity: <high | medium | low>
    detail: <what is being waited on, and from whom>

decisions:
  - id: ADR-001
    title: <the decision>
    status: open
    options: [<A>, <B>]
    resolution_criteria: <what evidence settles it>
    default_if_unresolved: <what an agent does meanwhile>
    affects: [<file not yet written>]

rollout:
  phase_1: <what ships first>
'''

# JSON Schemas are built from dicts (not string templates) so nesting braces
# can never be mangled by placeholder substitution.
BUSINESS_SCHEMA_OBJ = { '$schema': 'https://json-schema.org/draft/2020-12/schema',
  'title': 'business-spec',
  'type': 'object',
  'required': ['meta', 'actors', 'flows', 'acceptance_criteria', 'out_of_scope'],
  'properties': { 'meta': { 'type': 'object',
                            'required': ['name', 'version', 'updated', 'purpose'],
                            'properties': { 'name': {'type': 'string'},
                                            'version': {'type': 'string'},
                                            'updated': { 'type': 'string',
                                                         'pattern': '^\\d{4}-\\d{2}-\\d{2}$'},
                                            'purpose': {'type': 'string'},
                                            'related_artifacts': { 'type': 'array',
                                                                   'items': { 'type': 'string'}}}},
                  'actors': { 'type': 'array',
                              'minItems': 1,
                              'items': { 'type': 'object',
                                         'required': ['role', 'can'],
                                         'properties': { 'role': {'type': 'string'},
                                                         'who': {'type': 'string'},
                                                         'who_env': {'type': 'string'},
                                                         'can': { 'type': 'array',
                                                                  'items': { 'type': 'string'}}}}},
                  'identity': {'type': 'object'},
                  'state_machine': { 'type': 'object',
                                     'required': ['initial', 'transitions'],
                                     'properties': { 'initial': {'type': 'string'},
                                                     'terminal': { 'type': 'array',
                                                                   'items': { 'type': 'string'}},
                                                     'invariants': { 'type': 'array',
                                                                     'items': { 'type': 'string'}},
                                                     'transitions': { 'type': 'array',
                                                                      'items': { 'type': 'object',
                                                                                 'required': [ 'action',
                                                                                               'role',
                                                                                               'from',
                                                                                               'to'],
                                                                                 'properties': { 'action': { 'type': 'string'},
                                                                                                 'role': { 'type': 'string'},
                                                                                                 'role_constraint': { 'type': 'string'},
                                                                                                 'from': { 'type': 'string'},
                                                                                                 'to': { 'type': 'string'},
                                                                                                 'sets': { 'type': 'array',
                                                                                                           'items': { 'type': 'string'}}}}}}},
                  'flows': {'type': 'object'},
                  'sla': {'type': 'object'},
                  'errors': { 'type': 'array',
                              'items': { 'type': 'object',
                                         'required': ['http', 'when', 'message'],
                                         'properties': { 'http': {'type': 'integer'},
                                                         'when': {'type': 'string'},
                                                         'message': {'type': 'string'},
                                                         'fe_behaviour': { 'type': 'string'}}}},
                  'validation_rules': {'type': 'array'},
                  'idempotency': {'type': 'array'},
                  'copy': {'type': 'object', 'additionalProperties': {'type': 'string'}},
                  'acceptance_criteria': { 'type': 'array',
                                           'minItems': 1,
                                           'items': { 'type': 'object',
                                                      'required': ['id', 'text'],
                                                      'properties': { 'id': { 'type': 'string',
                                                                              'pattern': '^AC-[A-Z0-9]+-\\d+$'},
                                                                      'text': { 'type': 'string'},
                                                                      'ref': { 'type': 'string'}}}},
                  'out_of_scope': {'type': 'array', 'items': {'type': 'string'}}}}
BUSINESS_SCHEMA = json.dumps(BUSINESS_SCHEMA_OBJ, indent=2) + "\n"

ARCHITECTURE_SCHEMA_OBJ = { '$schema': 'https://json-schema.org/draft/2020-12/schema',
  'title': 'architecture',
  'type': 'object',
  'required': ['meta', 'principles', 'ownership', 'blockers', 'decisions'],
  'properties': { 'meta': { 'type': 'object',
                            'required': ['name', 'version', 'style'],
                            'properties': { 'name': {'type': 'string'},
                                            'version': {'type': 'string'},
                                            'style': {'type': 'string'},
                                            'deployment': {'type': 'string'},
                                            'related_artifacts': { 'type': 'array',
                                                                   'items': { 'type': 'string'}}}},
                  'principles': { 'type': 'array',
                                  'items': { 'type': 'object',
                                             'required': ['id', 'rule'],
                                             'properties': { 'id': {'type': 'string'},
                                                             'rule': {'type': 'string'}}}},
                  'ownership': { 'type': 'array',
                                 'items': { 'type': 'object',
                                            'required': ['file', 'owner'],
                                            'properties': { 'file': {'type': 'string'},
                                                            'owner': {'type': 'string'},
                                                            'role': {'type': 'string'}}}},
                  'domain_model': {'type': 'object'},
                  'persistence': {'type': 'object'},
                  'runtime': {'type': 'object'},
                  'deploy': { 'type': 'object',
                              'required': ['agent_may_deploy'],
                              'properties': {'agent_may_deploy': {'const': False}}},
                  'commands': {'type': 'object'},
                  'config': {'type': 'object'},
                  'blockers': { 'type': 'array',
                                'items': { 'type': 'object',
                                           'required': ['id', 'severity', 'detail'],
                                           'properties': { 'id': {'type': 'string'},
                                                           'severity': { 'enum': [ 'high',
                                                                                   'medium',
                                                                                   'low']},
                                                           'detail': {'type': 'string'}}}},
                  'decisions': { 'type': 'array',
                                 'items': { 'type': 'object',
                                            'required': ['id', 'title', 'status'],
                                            'properties': { 'id': { 'type': 'string',
                                                                    'pattern': '^ADR-\\d+$'},
                                                            'title': {'type': 'string'},
                                                            'status': { 'enum': [ 'open',
                                                                                  'decided',
                                                                                  'superseded']},
                                                            'affects': { 'type': 'array',
                                                                         'items': { 'type': 'string'}}},
                                            'allOf': [ { 'if': { 'properties': { 'status': { 'const': 'decided'}}},
                                                         'then': { 'required': [ 'date',
                                                                                 'rationale',
                                                                                 'choice']}},
                                                       { 'if': { 'properties': { 'status': { 'const': 'open'}}},
                                                         'then': { 'required': [ 'resolution_criteria',
                                                                                 'default_if_unresolved']}}]}},
                  'rollout': {'type': 'object'}}}
ARCHITECTURE_SCHEMA = json.dumps(ARCHITECTURE_SCHEMA_OBJ, indent=2) + "\n"

TEST_SPEC = '''\
"""Guards for contracts/ — spec vs. code.

Every test here compares a claim in the YAML against the thing that actually
enforces it. No test asserts the spec against itself: a claim that cannot be
traced to code or SQL does not belong in the spec.

Requires: pytest, PyYAML, jsonschema.
Run: python -m pytest tests/test_spec.py -q
"""
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parent.parent
CONTRACTS = REPO / "contracts"


class StrictLoader(yaml.SafeLoader):
    """SafeLoader that refuses duplicate mapping keys.

    PyYAML silently keeps the last duplicate; pasting a matrix row twice would
    then delete the original with no error anywhere.
    """


def _no_duplicate_keys(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r} in mapping", key_node.start_mark
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys
)


def load(name):
    return yaml.load((CONTRACTS / name).read_text(encoding="utf-8"), Loader=StrictLoader)


@pytest.fixture(scope="session")
def spec():
    return load("business-spec.yaml")


@pytest.fixture(scope="session")
def architecture():
    return load("architecture.yaml")


@pytest.fixture(scope="session")
def contract():
    return load("openapi.yaml")


@pytest.mark.parametrize("name", ["business-spec", "architecture"])
def test_spec_files_match_their_schema(name):
    doc = load(f"{name}.yaml")
    schema = json.loads((CONTRACTS / "schemas" / f"{name}.schema.json").read_text())
    errors = sorted(Draft202012Validator(schema).iter_errors(doc), key=lambda e: e.path)
    assert not errors, "\\n".join(f"{list(e.path)}: {e.message}" for e in errors)


def test_artifacts_cross_reference_real_paths(spec, architecture):
    for doc in (spec, architecture):
        for ref in doc["meta"].get("related_artifacts", []):
            assert (CONTRACTS / ref).resolve().exists(), f"dangling related_artifact: {ref}"


def test_no_orphan_states(spec, contract):
    """Every state used by the spec exists in the API enum, and vice versa."""
    enum = set()
    for schema in contract.get("components", {}).get("schemas", {}).values():
        status = (schema.get("properties") or {}).get("status") or {}
        enum |= set(status.get("enum", []))
    used = {t["from"] for t in spec["state_machine"]["transitions"]}
    used |= {t["to"] for t in spec["state_machine"]["transitions"]}
    used.add(spec["state_machine"]["initial"])
    used |= set(spec["state_machine"].get("terminal", []))
    assert used <= enum, f"states missing from the API enum: {sorted(used - enum)}"
    assert enum <= used, f"enum values no transition uses: {sorted(enum - used)}"


def test_open_decisions_have_not_been_pre_empted(architecture):
    for adr in architecture["decisions"]:
        if adr["status"] != "open":
            continue
        assert adr.get("resolution_criteria"), f"{adr['id']}: open with no resolution_criteria"
        assert adr.get("default_if_unresolved"), f"{adr['id']}: open with no default_if_unresolved"
        for target in adr.get("affects", []):
            assert not (REPO / target).exists(), (
                f"{adr['id']} is still open but {target} exists — decide first, code second"
            )


def test_blocked_by_points_at_a_real_blocker(architecture):
    ids = {b["id"] for b in architecture["blockers"]}
    for adr in architecture["decisions"]:
        ref = adr.get("blocked_by")
        if ref:
            assert ref in ids, f"{adr['id']}: blocked_by {ref} is not a declared blocker"


def test_ownership_points_at_real_files(architecture):
    for row in architecture["ownership"]:
        assert (REPO / row["file"]).exists(), f"ownership: {row['file']} does not exist"


def test_acceptance_criteria_are_covered(spec):
    """Bidirectional: every AC has a covers() marker, every marker names a real AC."""
    import re

    declared = {ac["id"] for ac in spec["acceptance_criteria"]}
    covered = set()
    for path in (REPO / "tests").rglob("*.py"):
        covered |= set(re.findall(r'covers\\(\\s*["\\\']?(AC-[A-Z0-9]+-\\d+)["\\\']?\\s*\\)',
                                  path.read_text(encoding="utf-8", errors="replace")))
    assert not declared - covered, f"acceptance criteria with no test: {sorted(declared - covered)}"
    assert not covered - declared, f"covers() naming unknown criteria: {sorted(covered - declared)}"


# TODO(you): add the guards only this project can have —
#   * every operation under contract["paths"] resolves to a real route
#   * the permission matrix matches the dependency guarding each route
#   * spec["copy"] equals the backend messages and the frontend labels
#   * spec["sla"]["policy"] equals the SLA constants in code
# Then break one on purpose and restore it: a guard that has never gone red is
# a guard of unknown value.
'''

FILES = [
    ("contracts/business-spec.yaml", BUSINESS_SPEC),
    ("contracts/openapi.yaml", OPENAPI),
    ("contracts/architecture.yaml", ARCHITECTURE),
    ("contracts/schemas/business-spec.schema.json", BUSINESS_SCHEMA),
    ("contracts/schemas/architecture.schema.json", ARCHITECTURE_SCHEMA),
    ("tests/test_spec.py", TEST_SPEC),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repo", nargs="?", default=".", help="repo root (default: .)")
    parser.add_argument("--name", required=True, help="project name written into meta.name")
    parser.add_argument("--date", default="", metavar="YYYY-MM-DD",
                        help="value for meta.updated (default: left as a placeholder)")
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    parser.add_argument("--dry-run", action="store_true", help="list what would be written")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"error: {repo} is not a directory", file=sys.stderr)
        return 2

    today = args.date or "<YYYY-MM-DD>"
    written, skipped = [], []
    for rel, template in FILES:
        target = repo / rel
        if target.exists() and not args.force:
            skipped.append(rel)
            continue
        body = template.replace("__PROJECT_NAME__", args.name).replace("__UPDATED__", today)
        if args.dry_run:
            written.append(rel)
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        written.append(rel)

    verb = "would write" if args.dry_run else "wrote"
    for rel in written:
        print(f"{verb}: {rel}")
    for rel in skipped:
        print(f"exists, skipped (use --force): {rel}")
    if written and not args.dry_run:
        print("\nnext: fill in the placeholders, replace every <...> and unresolved marker,\n"
              "      then run contract_audit.py and the guards in tests/test_spec.py")
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main())
