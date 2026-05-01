from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path


class GitHelper:
    def __init__(self, repo_path: Path, git_bin: str | None = None) -> None:
        self.repo_path = repo_path
        self.git_bin = git_bin or os.getenv("GIT_BIN", "git")

    def _run(self, *args: str) -> str:
        try:
            completed = subprocess.run(
                [self.git_bin, *args],
                cwd=self.repo_path,
                check=True,
                text=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            command = self.shell_join([self.git_bin, *args])
            stdout = (exc.stdout or "").strip()
            stderr = (exc.stderr or "").strip()
            details = [f"Git command failed: {command}"]
            if stdout:
                details.append(f"stdout:\n{stdout}")
            if stderr:
                details.append(f"stderr:\n{stderr}")
            raise RuntimeError("\n\n".join(details)) from exc
        return completed.stdout.strip()

    def ensure_identity(self, name: str, email: str) -> None:
        self._run("config", "user.name", name)
        self._run("config", "user.email", email)

    def create_or_reset_branch(self, branch_name: str) -> None:
        self._run("checkout", "-B", branch_name)

    def status_porcelain(self) -> str:
        return self._run("status", "--short")

    def commit_all(self, message: str) -> None:
        self._run("add", ".")
        if not self.status_porcelain():
            raise RuntimeError("No file changes were produced by the agent.")
        self._run("commit", "-m", message)

    def push_branch(self, branch_name: str) -> None:
        self._run("push", "--set-upstream", "origin", f"HEAD:refs/heads/{branch_name}")

    @staticmethod
    def shell_join(parts: list[str]) -> str:
        return " ".join(shlex.quote(part) for part in parts)
