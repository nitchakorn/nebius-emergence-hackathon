"""LLM client factory + the agentic investigation loop.

The model orchestrates: given the tools (backed by ToolExecutor) it discovers the schema,
forms and tests hypotheses, follows the evidence, and writes the final report. Talks to
Nebius Token Factory's OpenAI-compatible endpoint (NEBIUS_API_KEY), not Anthropic directly
— see config.NEBIUS_BASE_URL / config.NEBIUS_MODEL.
"""
import json
import os
from typing import Callable

from . import config, prompts
from .tools import TOOL_DEFINITIONS


def make_client():
    """OpenAI SDK pointed at the Nebius Token Factory endpoint. Reads NEBIUS_API_KEY."""
    from openai import OpenAI

    api_key = os.environ.get("NEBIUS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "NEBIUS_API_KEY is not set. Get a key from https://tokenfactory.nebius.com/ "
            "and `export NEBIUS_API_KEY=...` before running."
        )
    return OpenAI(base_url=config.NEBIUS_BASE_URL, api_key=api_key)


async def run_investigation(
    executor,
    question: str,
    *,
    model: str = config.NEBIUS_MODEL,
    max_turns: int = 60,
    on_event: Callable[[str, str], None] | None = None,
    context: str | None = None,
) -> str:
    """Drive the investigation loop until the model stops calling tools.

    Returns the final report text. `executor` is a ToolExecutor whose side effects
    (sql_log, collected, chart_paths, notes) accumulate as the model works.

    on_event(kind, detail) is called for each step: kind is one of
    "note" | "tool" | "status"; detail is the human-readable text.

    context, if given, is a plain-text summary of data the user is already looking at
    (e.g. a dashboard snapshot) — folded into the user message so the model treats it as
    known baseline instead of rediscovering it.
    """
    def emit(kind: str, detail: str) -> None:
        if on_event:
            on_event(kind, detail)

    client = make_client()
    system = prompts.system_prompt()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompts.user_message(question, context)},
    ]

    for _ in range(max_turns):
        resp = client.chat.completions.create(
            model=model,
            max_tokens=8000,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            messages=messages,
        )
        choice = resp.choices[0]
        message = choice.message

        assistant_msg = {"role": "assistant", "content": message.content}
        if message.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in (message.tool_calls or [])
            ]
        messages.append(assistant_msg)

        # No tool calls → the model is done; its text is the report. (Key off tool_calls
        # presence, not finish_reason: a turn can carry tool_calls AND hit the length cap.)
        if not message.tool_calls:
            report = message.content or ""
            if report.strip():
                return report
            # Empty final turn (rare) — ask once more for the report, tools withheld.
            emit("status", "Composing final report…")
            return _compose_report(client, model, messages)

        truncated = choice.finish_reason == "length"
        for tc in message.tool_calls:
            name = tc.function.name
            try:
                tool_input = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError as e:
                result = f"ERROR: malformed tool arguments JSON: {e}"
            else:
                if truncated:
                    result = "ERROR: response truncated before the tool call completed; retry."
                elif name == "note":
                    # Narration: surface it, record it, no data-plane call.
                    thought = tool_input.get("thought", "")
                    emit("note", thought)
                    result = await executor.run("note", tool_input)
                else:
                    emit("tool", f"{name}: {_summarize_input(name, tool_input)}")
                    result = await executor.run(name, tool_input)
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "name": name, "content": result}
            )

    # Turn budget exhausted — compose the report with tools withheld.
    emit("status", "Composing report (turn budget reached)…")
    return _compose_report(client, model, messages)


def _compose_report(client, model, messages) -> str:
    resp = client.chat.completions.create(
        model=model,
        max_tokens=8000,
        messages=messages
        + [
            {
                "role": "user",
                "content": (
                    "Stop investigating and write your final report now, using the evidence "
                    "you gathered. Do not call any tools. Lead with the Answer, then Evidence, "
                    "Clinical interpretation, and Caveats."
                ),
            }
        ],
    )
    return resp.choices[0].message.content or ""


def _summarize_input(name: str, tool_input: dict) -> str:
    """Short preview of a tool call for the live trace."""
    if name == "search_schema":
        return tool_input.get("query", "")
    if name == "get_schema":
        return tool_input.get("fqn", "").split(".")[-1]
    if name == "sample_data":
        return tool_input.get("table_fqn", "").split(".")[-1]
    if name == "generate_sql":
        q = tool_input.get("question", "")
        return q if len(q) <= 90 else q[:87] + "..."
    if name == "execute_query":
        return "running query"
    if name == "get_result_page":
        return "reading results"
    if name == "generate_plotly_chart":
        opts = tool_input.get("options") or {}
        return opts.get("title", tool_input.get("chart_type", "chart"))
    return ""
