"""Skills extension support"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Skill:
    """Represents a skill that can be used by the agent"""

    name: str
    description: str
    version: str
    path: Path

    @classmethod
    def from_file(cls, path: Path) -> "Skill":
        """Load a skill from a YAML file"""
        import yaml

        with open(path / "skill.yaml", encoding="utf-8") as f:
            data: dict = yaml.safe_load(f)

        return cls(
            name=data.get("name", path.name) or path.name,
            description=data.get("description", "") or "",
            version=data.get("version", "1.0.0") or "1.0.0",
            path=path,
        )


@dataclass
class SkillExtension:
    """Manages skills available to the workspace agent"""

    skills_path: Path | None = field(default=None)
    _skills: dict[str, Skill] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.skills_path is None:
            self.skills_path = Path("./skills")

    def load_skills(self) -> dict[str, Skill]:
        """Load all skills from the skills directory"""
        if not self.skills_path:
            return {}

        if not self.skills_path.exists():
            return {}

        skills: dict[str, Skill] = {}
        for skill_path in self.skills_path.iterdir():
            if skill_path.is_dir() and (skill_path / "skill.yaml").exists():
                skill = Skill.from_file(skill_path)
                skills[skill.name] = skill

        self._skills = skills
        return skills

    def get_skill_context(self, skill_name: str) -> str | None:
        """Get the context to inject for a skill"""
        skill = self._skills.get(skill_name)
        if not skill:
            return None

        # Read skill documentation
        readme_path = skill.path / "README.md"
        if readme_path.exists():
            return readme_path.read_text()

        return None
