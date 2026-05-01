from __future__ import annotations

import argparse
import os
import re
from pathlib import Path



def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:40] or "update"


def build_branch_name(pr_number: int, issue_summary: str) -> str:
    slug = slugify(issue_summary)
    run_id = os.getenv("GITHUB_RUN_ID")
    suffix = run_id or "manual"
    return f"pr-fix/pr-{pr_number}-{slug}-{suffix}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the LangChain PR fix agent.")
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--issue-summary", required=True)
    parser.add_argument("--repo-path", default=".")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    parser.add_argument(
        "--run-tests-command",
        default="python -m unittest discover -s sevflow-app/tests -p \"test_*.py\"",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def build_pr_body(original_pr_url: str, issue_summary: str, fix_summary: str) -> str:
    return (
        f"## What this fixes\n"
        f"- Follow-up for {original_pr_url}\n"
        f"- Reported issue: {issue_summary}\n"
        f"- Applied fix: {fix_summary}\n"
    )


def main() -> None:
    from .agent import run_fix_agent
    from .git_helper import GitHelper
    from .github_api import GitHubClient
    from .session import AgentSession

    args = parse_args()
    repo_path = Path(args.repo_path).resolve()

    github_token = require_env("GITHUB_TOKEN")
    require_env("OPENAI_API_KEY")
    repository = require_env("GITHUB_REPOSITORY")
    
    require_env("LANGSMITH_TRACING")
    require_env("LANGSMITH_API_KEY")
    require_env("LANGSMITH_PROJECT")

    github = GitHubClient(token=github_token, repository=repository)
    pr = github.get_pull_request(args.pr_number)

    session = AgentSession(
        repo_path=repo_path,
        pr=pr,
        issue_summary=args.issue_summary,
        run_tests_command=args.run_tests_command,
    )

    fix_summary = run_fix_agent(session=session, model_name=args.model)
    if not session.modified_files:
        raise RuntimeError("The agent finished without modifying any files.")

    branch_name = build_branch_name(pr.number, args.issue_summary)
    commit_message = f"fix: address PR #{pr.number} feedback"

    print(f"Agent summary: {fix_summary}")
    print(f"Modified files: {sorted(session.modified_files)}")

    if args.dry_run:
        print("Dry run enabled. Skipping git push and pull request creation.")
        return

    git = GitHelper(repo_path=repo_path)
    git.ensure_identity("github-actions[bot]", "41898282+github-actions[bot]@users.noreply.github.com")
    git.create_or_reset_branch(branch_name)
    git.commit_all(commit_message)
    git.push_branch(branch_name)

    created_pr = github.create_pull_request(
        title=f"fix: address PR #{pr.number} issue",
        body=build_pr_body(pr.html_url, args.issue_summary, fix_summary),
        head=branch_name,
        base=pr.base_ref,
    )
    print(f"Created PR: {created_pr['html_url']}")


if __name__ == "__main__":
    main()
