# Contract First — Agent Entry Point

This repository packages the **Contract First** skill in a multi-provider layout compatible with Antigravity (`agy`), Claude Code, Codex, Cursor, Gemini CLI, OpenCode, Hermes, and the universal Agent Skills standard.

## Skill Location

- Primary skill instructions: `skills/contract-first/SKILL.md`
- Progressive-disclosure references: `skills/contract-first/references/`
- Zero-dependency CLI scripts (Python 3 stdlib only):
  - `skills/contract-first/scripts/scaffold_contracts.py`
  - `skills/contract-first/scripts/contract_audit.py`

## Contributing / Verification

Before committing changes to this repository:

1. Keep `version` synchronized across every plugin manifest (`.antigravity-plugin/plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `gemini-extension.json`).
2. Keep `skills/contract-first/SKILL.md` provider- and model-agnostic — never hardcode harness-specific tool names or single-vendor models.
3. Run the layout & script smoke test suite:

```bash
python3 -m unittest discover -s tests -v
```
