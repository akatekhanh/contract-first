# `contracts/openapi.yaml` — API + entity model

OpenAPI 3.1, YAML, hand-written (not generated from code — the direction is contract → code).

## Rules

- **Every entity is a component schema** with a complete `required` list. Enums for every status/type. Nullable is `type: [string, "null"]` (3.1 style, not `nullable: true`).
- **Union / polymorphic schemas MUST carry a `discriminator` with an explicit `mapping`.** Without the mapping, `openapi-typescript` emits the wrong const union — a real bug that has cost real hours here.
- **One Problem shape for all errors**: `{detail: string | string[]}`. Declare 403/404/409/422 on every operation that has a permission gate, an optimistic lock, or validation.
- `servers` and `tags` present; every operation has a unique `operationId`.
- **Declare how the user is identified as a `securitySchemes` entry** — even when identity is injected by a proxy header. Implicit identity is the single most common piece of tribal knowledge that never makes it into a contract.
- **Unimplemented operations go in a root `x-planned-operations` block**, not in `paths`. A PR that implements one *moves the whole block* into `paths`. This works because the guard asserts that every operation under `paths` resolves to a real route — so parking future work under `paths` would break the build, and hiding it in a comment would lose it.

## Two-way enforcement

**Backend**: entities mirror the component schemas one-to-one — same field names, same required set, same enums. A schema change is a code change in the same commit.

**Frontend**: types are generated, never hand-written.

```bash
npx openapi-typescript contracts/openapi.yaml -o src/types/schema.d.ts
```

Check `schema.d.ts` in, and let CI fail on drift:

```bash
npm run gen:api && git diff --exit-code src/types/schema.d.ts
```

That single gate is what makes the contract binding on the UI. Without it, generated types quietly become hand-maintained types.

## Cross-file consistency

`openapi.yaml` and `business-spec.yaml` share a vocabulary: statuses, actions, roles. The guard checks both directions —

- every status/action/role named in the spec exists in an OpenAPI enum, and
- every enum value in OpenAPI is described somewhere in the spec (no orphan enums, no orphan actions).

When they disagree, the spec wins on meaning and the contract wins on shape: fix the file that is describing the wrong thing, not whichever is easier to edit.
