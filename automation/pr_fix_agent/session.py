from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .github_api import PullRequestContext


SKIP_PARTS = {
    ".git",
    ".terraform",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "node_modules",
}


@dataclass
class AgentSession:
    repo_path: Path
    pr: "PullRequestContext"
    issue_summary: str
    run_tests_command: str
    modified_files: set[str] = field(default_factory=set)
    final_summary: str | None = None

    def __post_init__(self) -> None:
        self.repo_path = self.repo_path.resolve()

    def resolve_path(self, relative_path: str) -> Path:
        candidate = (self.repo_path / relative_path).resolve()
        repo_root = self.repo_path.resolve()
        if repo_root not in candidate.parents and candidate != repo_root:
            raise ValueError(f"Refusing to access file outside repo: {relative_path}")
        return candidate

    def list_files(self, limit: int = 200) -> list[str]:
        results: list[str] = []
        for path in self.repo_path.rglob("*"):
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            if path.is_file():
                results.append(path.relative_to(self.repo_path).as_posix())
            if len(results) >= limit:
                break
        return results

    def read_file(self, relative_path: str) -> str:
        return self.resolve_path(relative_path).read_text(encoding="utf-8")

    def write_file(self, relative_path: str, content: str) -> str:
        path = self.resolve_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self.modified_files.add(path.relative_to(self.repo_path).as_posix())
        return f"Wrote {path.relative_to(self.repo_path).as_posix()}"

    def search_text(self, query: str, limit: int = 20) -> list[dict[str, str | int]]:
        matches: list[dict[str, str | int]] = []
        lowered_query = query.lower()
        for relative_path in self.list_files(limit=1000):
            path = self.repo_path / relative_path
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for index, line in enumerate(lines, start=1):
                if lowered_query in line.lower():
                    matches.append({"path": relative_path, "line": index, "text": line.strip()})
                    if len(matches) >= limit:
                        return matches
        return matches

    def run_tests(self) -> str:
        completed = subprocess.run(
            self.run_tests_command,
            cwd=self.repo_path,
            shell=True,
            text=True,
            capture_output=True,
        )
        return json.dumps(
            {
                "command": self.run_tests_command,
                "returncode": completed.returncode,
                "stdout": completed.stdout[-6000:],
                "stderr": completed.stderr[-6000:],
            },
            indent=2,
        )
