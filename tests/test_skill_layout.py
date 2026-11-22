"""Layout, manifest, and end-to-end script guards for the contract-first skill repo.

Zero external dependencies (Python 3 stdlib unittest only).
Run: python3 -m unittest discover -s tests -v
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO / "skills" / "contract-first"

PLUGIN_MANIFESTS = [
    ".antigravity-plugin/plugin.json",
    ".claude-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
    "gemini-extension.json",
]

MARKETPLACE_MANIFESTS = [
    ".claude-plugin/marketplace.json",
    ".agents/plugins/marketplace.json",
]


class TestMultiProviderManifests(unittest.TestCase):
    def test_all_plugin_manifests_valid_and_version_synced(self):
        versions = {}
        for rel in PLUGIN_MANIFESTS:
            path = REPO / rel
            self.assertTrue(path.exists(), f"missing manifest: {rel}")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data.get("name"), "contract-first", f"{rel}: unexpected name")
            self.assertTrue(data.get("description"), f"{rel}: empty description")
            self.assertTrue(data.get("version"), f"{rel}: missing version")
            versions[rel] = data["version"]
            if "skills" in data:
                skills_path = (REPO / data["skills"]).resolve()
                self.assertTrue(skills_path.is_dir(), f"{rel}: skills path {data['skills']} missing")

        unique_versions = set(versions.values())
        self.assertEqual(
            len(unique_versions),
            1,
            f"version mismatch across manifests: {versions}",
        )

    def test_marketplace_manifests_valid(self):
        expected_version = json.loads(
            (REPO / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
        )["version"]
        for rel in MARKETPLACE_MANIFESTS:
            path = REPO / rel
            self.assertTrue(path.exists(), f"missing marketplace manifest: {rel}")
            data = json.loads(path.read_text(encoding="utf-8"))
            plugins = data.get("plugins", [])
            self.assertTrue(plugins, f"{rel}: no plugins declared")
            self.assertEqual(plugins[0].get("name"), "contract-first")
            if "version" in plugins[0]:
                self.assertEqual(plugins[0]["version"], expected_version)

    def test_gemini_and_agents_entry_points_exist(self):
        gemini_md = (REPO / "GEMINI.md").read_text(encoding="utf-8")
        self.assertIn("skills/contract-first/SKILL.md", gemini_md)
        agents_md = (REPO / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("skills/contract-first/SKILL.md", agents_md)


class TestSkillLayout(unittest.TestCase):
    def test_skill_frontmatter_and_referenced_files(self):
        skill_md = SKILL_DIR / "SKILL.md"
        self.assertTrue(skill_md.exists(), "missing skills/contract-first/SKILL.md")
        text = skill_md.read_text(encoding="utf-8")

        m = re.match(r"^---\n(.*?)\n---\n", text, flags=re.S)
        self.assertIsNotNone(m, "SKILL.md missing YAML frontmatter")
        fm = m.group(1)
        self.assertRegex(
            fm,
            r"(?m)^name:\s*contract-first\s*$",
            "frontmatter name must be contract-first",
        )
        self.assertIn("description:", fm)

        # Every referenced local file in SKILL.md must exist inside the skill directory
        for ref in re.findall(r"`((?:references|scripts)/[A-Za-z0-9_.-]+)`", text):
            self.assertTrue((SKILL_DIR / ref).exists(), f"dangling reference in SKILL.md: {ref}")

    def test_scripts_smoke_end_to_end(self):
        scaffold = SKILL_DIR / "scripts" / "scaffold_contracts.py"
        audit = SKILL_DIR / "scripts" / "contract_audit.py"
        with tempfile.TemporaryDirectory() as tmp:
            res = subprocess.run(
                [sys.executable, str(scaffold), tmp, "--name", "SmokeApp", "--date", "2026-11-22"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, f"scaffold failed: {res.stderr}")
            for expected in (
                "contracts/business-spec.yaml",
                "contracts/openapi.yaml",
                "contracts/architecture.yaml",
                "contracts/schemas/business-spec.schema.json",
                "contracts/schemas/architecture.schema.json",
                "tests/test_spec.py",
            ):
                self.assertTrue((Path(tmp) / expected).exists(), f"missing scaffolded file: {expected}")

            # Second run without --force must skip and exit 1
            res2 = subprocess.run(
                [sys.executable, str(scaffold), tmp, "--name", "SmokeApp"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res2.returncode, 1)

            # Audit runs cleanly (exit 1 expected on fresh placeholder scaffold, never exit 2)
            res3 = subprocess.run(
                [sys.executable, str(audit), tmp, "--severity", "HIGH"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                res3.returncode,
                0,
                f"fresh scaffold should have zero HIGH audit findings:\n{res3.stdout}\n{res3.stderr}",
            )


if __name__ == "__main__":
    unittest.main()
