# Enforcement — `tests/test_spec.py` and `tests/test_contract.py`

The contract is only worth having if it fails when it drifts. Every guard compares a claim in the YAML against the thing that actually enforces it — a route table, a DB constraint, a constant. **No test asserts the spec against itself.** If a claim cannot be traced to code or SQL, it does not belong in the spec.

## Minimum set of guards

- The artifacts exist and cross-reference each other with correct paths (`meta.related_artifacts`).
- **JSON Schema validation of the spec files themselves** — a wrong key or type fails immediately instead of surfacing as a `KeyError` in an unrelated test. Add `# yaml-language-server: $schema=…` as the first line so the IDE flags it while typing.
- **Strict YAML loading**: duplicate keys are an error (see below).
- **No YAML 1.1 implicit typing**: `NO/YES/ON/OFF/Y/N` becoming booleans, `1.10` becoming a float. Quote anything ambiguous; write booleans only as `true`/`false`.
- `state_machine.transitions` uses only statuses/actions/roles present in the enums, and each (role, from, action) triple matches the domain's real transition table.
- Every action in the API contract is described in the spec (no orphan actions), and every spec enum value exists in OpenAPI (no orphan enums).
- `sla.policy` equals the SLA constants in code.
- `copy` equals both the backend message strings and the frontend labels.
- AC ↔ `covers("AC-…")` markers, **both directions**: an AC with no test fails; a marker naming a nonexistent AC fails.
- ADRs: `decided` requires `date` + `rationale`; `open` requires `resolution_criteria` + `default_if_unresolved`; `blocked_by` must name an existing blocker; files listed in an open ADR's `affects` must not exist yet.
- `ownership` entries point at real files; routes and concepts declared in `architecture.yaml` are findable in the code.

## Strict loader (PyYAML keeps the last duplicate silently)

```python
import yaml


class StrictLoader(yaml.SafeLoader):
    """SafeLoader that refuses duplicate mapping keys."""


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
```

Without this, pasting a matrix row twice deletes the original and nothing anywhere complains — the exact failure mode a contract file must not have.

## Tracing pattern

Compare against the runtime object, not a copy of it:

```python
from fastapi.routing import APIRoute

def test_every_contract_operation_has_a_route(app, contract):
    live = {(r.path, m) for r in app.routes if isinstance(r, APIRoute) for m in r.methods}
    for path, ops in contract["paths"].items():
        for method in ops:
            assert (path, method.upper()) in live, f"{method.upper()} {path} is in the contract but has no route"
```

The same shape works for enums (against DB CHECK constraints or Python constants), for the permission matrix (against the dependency guarding each route), and for copy (against the module holding the strings).

## Verify the guard, not just the code

After writing each guard, **break it on purpose and restore it**. A guard that has never gone red is a guard of unknown value — and a guard that goes red in the wrong place (import error, fixture failure) teaches nothing when it eventually fires.

## CI wiring

Run in this order so failures are cheap first: schema validation of the YAML → `test_spec.py` → `test_contract.py` → type-generation drift gate (`gen:api && git diff --exit-code`) → the normal test suite and lint.
