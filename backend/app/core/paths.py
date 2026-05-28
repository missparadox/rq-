from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / ".agents" / "skills" / "requirements-evaluator"
SKILL_SCRIPTS_ROOT = SKILL_ROOT / "scripts"
SKILL_FILE = SKILL_ROOT / "SKILL.md"
REPORT_TEMPLATE_FILE = SKILL_ROOT / "references" / "report-template.md"
DEFAULT_RUBRIC_FILE = SKILL_ROOT / "references" / "default-rubric.md"
