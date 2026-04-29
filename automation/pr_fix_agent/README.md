# PR Fix Agent

This folder contains a LangChain-based automation that can:

- inspect a GitHub pull request
- read the files changed by that PR
- apply a minimal fix in the checked-out repository
- run local validation
- commit the result to a new branch
- open a follow-up pull request

## Requirements

- `OPENAI_API_KEY`
- `GITHUB_TOKEN`
- `GITHUB_REPOSITORY` in `owner/repo` format
- a writable Git checkout with `git` available on `PATH`

LangChain uses `langchain-openai`'s `ChatOpenAI` integration. Current LangChain docs recommend `langchain_openai.ChatOpenAI` instead of the older community OpenAI wrapper.

## Install

```bash
pip install -r automation/pr_fix_agent/requirements.txt
```

## Run

```bash
python -m automation.pr_fix_agent.main \
  --pr-number 42 \
  --issue-summary "The PR breaks the SevFlow metrics endpoint by returning malformed labels."
```

Optional flags:

- `--repo-path .`
- `--model gpt-4.1-mini`
- `--run-tests-command "python -m unittest discover -s sevflow-app/tests -p \"test_*.py\""`
- `--dry-run`

## Workflow

1. The script loads the PR metadata and changed-file patch from GitHub.
2. A LangChain tool-calling loop asks the model to inspect files, edit code, and run tests.
3. If files changed, the script creates a branch named like `pr-fix/pr-42-short-summary`.
4. The branch is pushed to `origin`.
5. A new pull request is opened against the original PR base branch.

## Notes

- The agent is intentionally constrained to repo file reads, repo file writes, PR context, and one validation command.
- It is best for narrow follow-up fixes, not large refactors.
- The workflow added in `.github/workflows/pr-fix-agent.yml` is the easiest way to trigger it from GitHub Actions.
