# Fan-out across several agents

The `ownership` table in `architecture.yaml` is the second contract: each file has exactly one owner, and the boundary lives in the file rather than in a sentence in a prompt. Prompt instructions are forgotten between sessions; a table that a test validates is not.

## Roles

| Agent | Owns | Must not |
|---|---|---|
| ARCHITECT | contracts, entities, ports/interfaces, shared signatures | — |
| AGENT-DOMAIN | pure logic + its tests | import a framework, change a shared signature |
| AGENT-ADAPTER | port implementations, DDL/migrations | touch the domain or the contract |
| AGENT-API | routes matching the contract, dependency injection | add an endpoint that is not in the contract |
| AGENT-FE | UI + types generated from the contract | invent a label outside `business-spec.yaml#copy` |

**The golden rule: an agent that finds the contract wrong REPORTS it — it does not edit it.** If anyone may edit the contract, the contract becomes a scratchpad and the whole pattern collapses.

## Matching work to model tier (multi-provider / multi-model)

The contract is model-agnostic: any provider or mixed-model swarm works as long as each role gets an appropriate reasoning tier and stays inside its owned files.

| Work type | Role | Model tier | Examples across providers |
|---|---|---|---|
| Lookup / "where is X" / read-only audit | `RESEARCH` | Fast / lightweight | Gemini Flash / Flash-Lite · Claude Haiku · GPT-5 mini / o4-mini |
| Implementing one layer against a settled contract | `AGENT-DOMAIN`, `AGENT-ADAPTER`, `AGENT-API`, `AGENT-FE` | Mid / balanced | Gemini Pro · Claude Sonnet · GPT-5 / Codex |
| Changing the contract, state machine, or an ADR | `ARCHITECT` | Frontier / high-reasoning | Gemini Pro / Neon (High) · Claude Opus · GPT-5 (high reasoning) |
| Diff review / contract verification | `REVIEWER` | **Separate agent** (different session or different model family) | Cross-model review (e.g., Gemini writes, Claude reviews — or vice versa) |

**Rule of thumb for review:** Whoever just wrote the code is the worst possible reviewer of it. Using a separate agent—or a different model family—catches blind spots that self-review misses.

## Sequencing a feature across agents

1. ARCHITECT updates `business-spec.yaml` → `openapi.yaml` → `architecture.yaml` (including new `ownership` rows) and the guards.
2. Guards run and fail — they now describe work not yet done.
3. DOMAIN, ADAPTER, API and FE agents run in parallel, each confined to its owned files.
4. A review agent checks the diff against the contract, not against its own taste.
5. Guards go green; the contract and code shipped in the same commit.

If step 1 is skipped, agents negotiate the interface through the code and you get four half-compatible versions of the same idea. That failure mode is the reason this skill exists.
