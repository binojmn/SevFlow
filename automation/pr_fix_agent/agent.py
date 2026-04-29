from __future__ import annotations

import json
from textwrap import dedent

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .session import AgentSession


class RepoFileInput(BaseModel):
    path: str = Field(..., description="Repo-relative file path.")


class WriteFileInput(BaseModel):
    path: str = Field(..., description="Repo-relative file path.")
    content: str = Field(..., description="Full replacement file content.")


class SearchInput(BaseModel):
    query: str = Field(..., description="Plain text query to search for in the repo.")


class ListFilesInput(BaseModel):
    limit: int = Field(default=200, ge=1, le=1000, description="Maximum file paths to return.")


class FinalizeInput(BaseModel):
    summary: str = Field(..., description="Short summary of the fix that was applied.")


def build_tools(session: AgentSession) -> list[StructuredTool]:
    def show_pr_context() -> str:
        return json.dumps(
            {
                "number": session.pr.number,
                "title": session.pr.title,
                "body": session.pr.body,
                "base_ref": session.pr.base_ref,
                "head_ref": session.pr.head_ref,
                "issue_summary": session.issue_summary,
                "html_url": session.pr.html_url,
                "files": [
                    {
                        "filename": file["filename"],
                        "status": file["status"],
                        "patch": file.get("patch", ""),
                    }
                    for file in session.pr.files
                ],
            },
            indent=2,
        )

    def list_files(limit: int = 200) -> str:
        return json.dumps(session.list_files(limit=limit), indent=2)

    def read_file(path: str) -> str:
        return session.read_file(path)

    def search_repo(query: str) -> str:
        return json.dumps(session.search_text(query), indent=2)

    def write_file(path: str, content: str) -> str:
        return session.write_file(path, content)

    def run_tests() -> str:
        return session.run_tests()

    def finalize_fix(summary: str) -> str:
        session.final_summary = summary
        return f"Finalized: {summary}"

    return [
        StructuredTool.from_function(show_pr_context, description="Return the PR metadata, changed files, and issue summary."),
        StructuredTool.from_function(list_files, args_schema=ListFilesInput, description="List repo files when you need more context."),
        StructuredTool.from_function(read_file, args_schema=RepoFileInput, description="Read a repo file."),
        StructuredTool.from_function(search_repo, args_schema=SearchInput, description="Search plain text across repo files."),
        StructuredTool.from_function(write_file, args_schema=WriteFileInput, description="Replace a repo file with updated content."),
        StructuredTool.from_function(run_tests, description="Run the configured test or validation command and return stdout/stderr."),
        StructuredTool.from_function(finalize_fix, args_schema=FinalizeInput, description="Call this only after the fix is complete and validated as much as possible."),
    ]


def run_fix_agent(session: AgentSession, model_name: str) -> str:
    tools = build_tools(session)
    llm = ChatOpenAI(model=model_name, temperature=0)
    llm_with_tools = llm.bind_tools(tools)

    system_prompt = dedent(
        """
        You are a senior GitHub remediation agent working inside a checked out repository.
        Your job is to inspect the referenced pull request, understand the reported issue, apply the smallest safe fix, and validate it.

        Rules:
        - Start by calling `show_pr_context`.
        - Read the files touched by the PR before editing anything.
        - Keep fixes minimal and directly tied to the issue summary.
        - Prefer editing existing code over introducing new architecture.
        - Run validation with `run_tests` before finalizing when possible.
        - Use `write_file` with the full final file content.
        - End by calling `finalize_fix`.
        """
    ).strip()

    conversation = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"Fix the problem reported for pull request #{session.pr.number}.\n"
                f"Issue summary: {session.issue_summary}\n"
                "Work in the local repository checkout and only change what is needed."
            )
        ),
    ]

    for _ in range(20):
        response = llm_with_tools.invoke(conversation)
        conversation.append(response)

        tool_calls = getattr(response, "tool_calls", [])
        if not tool_calls:
            break

        for tool_call in tool_calls:
            tool = next(tool for tool in tools if tool.name == tool_call["name"])
            result = tool.invoke(tool_call["args"])
            conversation.append(
                ToolMessage(content=str(result), tool_call_id=tool_call["id"])
            )
            if tool.name == "finalize_fix":
                return session.final_summary or "Fix completed."

    if session.final_summary:
        return session.final_summary

    if isinstance(conversation[-1], AIMessage):
        return str(conversation[-1].content)
    return "Agent finished without a final summary."
