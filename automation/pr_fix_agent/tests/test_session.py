from dataclasses import dataclass
from pathlib import Path
import shutil
import unittest

from automation.pr_fix_agent.main import slugify
from automation.pr_fix_agent.session import AgentSession


@dataclass
class PullRequestContextStub:
    number: int
    title: str
    body: str
    base_ref: str
    head_ref: str
    head_sha: str
    author: str
    files: list
    html_url: str


def build_pr_context() -> PullRequestContextStub:
    return PullRequestContextStub(
        number=7,
        title="Sample PR",
        body="Body",
        base_ref="main",
        head_ref="feature/sample",
        head_sha="abc123",
        author="octocat",
        files=[],
        html_url="https://github.com/example/repo/pull/7",
    )


class AgentSessionTests(unittest.TestCase):
    def make_repo_dir(self, name: str) -> Path:
        repo_dir = Path("automation/pr_fix_agent/.agent-workspace") / name
        if repo_dir.exists():
            shutil.rmtree(repo_dir)
        repo_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(repo_dir, ignore_errors=True))
        return repo_dir

    def test_slugify_trims_and_normalizes(self) -> None:
        self.assertEqual(slugify("Fix metrics labels now!"), "fix-metrics-labels-now")

    def test_write_file_tracks_modified_path(self) -> None:
        repo_dir = self.make_repo_dir("write-file")
        session = AgentSession(
            repo_path=repo_dir,
            pr=build_pr_context(),
            issue_summary="Example issue",
            run_tests_command="echo ok",
        )

        result = session.write_file("notes/output.txt", "hello")

        self.assertIn("notes/output.txt", result)
        self.assertEqual(session.read_file("notes/output.txt"), "hello")
        self.assertEqual(session.modified_files, {"notes/output.txt"})

    def test_resolve_path_blocks_parent_escape(self) -> None:
        repo_dir = self.make_repo_dir("path-escape")
        session = AgentSession(
            repo_path=repo_dir,
            pr=build_pr_context(),
            issue_summary="Example issue",
            run_tests_command="echo ok",
        )

        with self.assertRaises(ValueError):
            session.resolve_path("../outside.txt")


if __name__ == "__main__":
    unittest.main()
