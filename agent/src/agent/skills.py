"""SkillsLoader: loads scenario guides from the skills/ directory.

Uses progressive disclosure:
- System prompt only injects one-line summaries (get_descriptions).
- Full docs loaded on demand (get_content, called by the load_skill tool).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Skill:
    """Single skill definition.

    Attributes:
        name: Skill name.
        description: Skill description.
        category: Skill category for grouped display.
        body: SKILL.md body text.
        dir_path: Skill directory path (used for on-demand loading of supporting files).
        metadata: Parsed frontmatter metadata.
        source: "builtin" or "user" — where the skill was loaded from.
    """

    name: str
    description: str = ""
    category: str = "other"
    body: str = ""
    dir_path: Optional[Path] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = "builtin"

    def load_support_file(self, filename: str) -> Optional[str]:
        """Load a supporting file on demand.

        Args:
            filename: File name (e.g. examples.md).

        Returns:
            File content or None.
        """
        if not self.dir_path:
            return None
        path = self.dir_path / filename
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            logger.debug("Failed to read skill: %s", path, exc_info=True)
            return None


from src.agent.frontmatter import parse_frontmatter as _parse_frontmatter  # shared util


def _load_skill_dir(dir_path: Path) -> Optional[Skill]:
    """Load a skill from a directory.

    Args:
        dir_path: Skill directory path (must contain SKILL.md).

    Returns:
        Skill instance or None.
    """
    skill_file = dir_path / "SKILL.md"
    if not skill_file.exists():
        return None
    try:
        text = skill_file.read_text(encoding="utf-8")
    except Exception:
        logger.debug("Failed to read skill file: %s", skill_file, exc_info=True)
        return None

    meta, body = _parse_frontmatter(text)
    name = meta.get("name", dir_path.name)
    if not name:
        return None

    return Skill(
        name=name,
        description=meta.get("description", ""),
        category=meta.get("category", "other"),
        body=body,
        dir_path=dir_path,
        metadata=meta,
    )


USER_SKILLS_BASE = Path.home() / ".AStockPursue" / "skills"
USER_SKILLS_DIR = USER_SKILLS_BASE / "1"  # backward-compat: default user


def _user_skills_dir(user_id: int) -> Path:
    return USER_SKILLS_BASE / str(user_id)


class SkillsLoader:
    """Load skills from bundled skills/ directory and per-user skills directory.

    Attributes:
        skills: Loaded skill list (bundled + user-created).
    """

    def __init__(self, skills_dir: Optional[Path] = None,
                 user_skills_dir: Optional[Path] = None,
                 user_id: int = 1,
                 disabled_skills: Optional[set[str]] = None) -> None:
        """Initialize SkillsLoader.

        Args:
            skills_dir: Bundled skills directory path; defaults to agent/skills/.
            user_skills_dir: Override user skills directory (for testing).
            user_id: User ID for per-user skill isolation.
            disabled_skills: Set of skill names to exclude from loading.
        """
        self.skills_dir = skills_dir or Path(__file__).resolve().parents[1] / "skills"
        self._user_skills_dir = user_skills_dir or _user_skills_dir(user_id)
        self._user_id = user_id
        self._disabled = disabled_skills or set()
        self.skills: List[Skill] = []
        self._load()

    def _load(self) -> None:
        """Load all skill subdirectories from user and bundled directories.

        User skills are loaded first so they override bundled skills with the same name
        (e.g. after patch_skill copies and modifies a bundled skill).
        Skills in the disabled set are skipped.
        """
        seen_names: set[str] = set()
        for directory, source in ((self._user_skills_dir, "user"), (self.skills_dir, "builtin")):
            if not directory or not directory.exists():
                continue
            for path in sorted(directory.iterdir()):
                if path.is_dir() and (path / "SKILL.md").exists():
                    skill = _load_skill_dir(path)
                    if skill and skill.name not in seen_names and skill.name not in self._disabled:
                        skill.source = source
                        self.skills.append(skill)
                        seen_names.add(skill.name)

    # Display order for categories (unlisted categories appear at the end).
    _CATEGORY_ORDER = [
        "data-source", "strategy", "analysis", "asset-class",
        "crypto", "flow", "tool", "other",
    ]

    def get_descriptions(self) -> str:
        """Return skills grouped by category for the system prompt.

        Returns:
            Grouped skill list with category headers.
        """
        if not self.skills:
            return "(no skills)"

        groups: Dict[str, List[Skill]] = {}
        for skill in self.skills:
            groups.setdefault(skill.category, []).append(skill)

        ordered_cats = [c for c in self._CATEGORY_ORDER if c in groups]
        ordered_cats += [c for c in sorted(groups) if c not in ordered_cats]

        lines: List[str] = []
        for cat in ordered_cats:
            lines.append(f"\n### {cat}")
            for skill in groups[cat]:
                lines.append(f"  - {skill.name}: {skill.description}")
        return "\n".join(lines)

    def get_content(self, name: str) -> str:
        """Return the full documentation for a skill (used by the load_skill tool).

        Falls back to disk lookup for user skills created mid-session.

        Args:
            name: Skill name.

        Returns:
            XML-wrapped full skill document, or an error message.
        """
        for skill in self.skills:
            if skill.name == name:
                return f'<skill name="{name}">\n{skill.body}\n</skill>'

        # Fallback: check user skills directory on disk (mid-session created skills)
        usd = self._user_skills_dir
        if usd:
            skill = _load_skill_dir(usd / name)
            if skill:
                self.skills.append(skill)
                return f'<skill name="{name}">\n{skill.body}\n</skill>'

        available = ", ".join(s.name for s in self.skills)
        return f"Error: Unknown skill '{name}'. Available: {available}"
