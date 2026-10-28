"""
Streamlit front end that runs a Claude Code skill on an uploaded PDF
and returns the PDF the skill produces.

Run with:  streamlit run app.py
Requires:  ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN in your environment or .env
"""

import asyncio
import shutil
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import find_dotenv, load_dotenv
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

load_dotenv(find_dotenv())

RUNS_DIR = Path(__file__).parent / "runs"


# ---------------------------------------------------------------------------
# Workspace setup: each run gets its own folder with the skill, input and output
# ---------------------------------------------------------------------------
def prepare_workspace(skill_dir: Path, uploaded_file) -> tuple[Path, str]:
    run_dir = RUNS_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")
    (run_dir / "input").mkdir(parents=True)
    (run_dir / "output").mkdir()

    # Copy the skill into the run folder's project skills directory.
    # The SDK discovers skills in <cwd>/.claude/skills/<name>/SKILL.md,
    # and the folder name becomes the /command name.
    skill_name = skill_dir.name
    shutil.copytree(skill_dir, run_dir / ".claude" / "skills" / skill_name)

    # Save the uploaded PDF
    (run_dir / "input" / uploaded_file.name).write_bytes(uploaded_file.getvalue())

    return run_dir, skill_name


# ---------------------------------------------------------------------------
# Safety hook: block shell commands that reach outside the run folder
# ---------------------------------------------------------------------------
BLOCKED_PATTERNS = ["rm -rf /", "rm -rf ~", "sudo ", "curl ", "wget ", "> /dev/"]


async def guard_bash(input_data, tool_use_id, context):
    command = input_data.get("tool_input", {}).get("command", "")
    if any(p in command for p in BLOCKED_PATTERNS):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Command not allowed in this tool.",
            }
        }
    return {}


# ---------------------------------------------------------------------------
# Run the agent and stream progress into the UI
# ---------------------------------------------------------------------------
async def run_skill(run_dir: Path, skill_name: str, filename: str, instructions: str, log):
    prompt = (
        f"/{skill_name} "
        f"The input PDF is at input/{filename}. "
        f"{instructions.strip()} "
        "Save the final PDF in the output/ folder."
    )

    options = ClaudeAgentOptions(
        cwd=str(run_dir),
        setting_sources=["project"],  # load only the skill copied into this run
        allowed_tools=["Skill", "Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        max_turns=40,
        hooks={"PreToolUse": [HookMatcher(matcher="Bash", hooks=[guard_bash])]},
    )

    result = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    log.markdown(block.text)
                elif isinstance(block, ToolUseBlock):
                    detail = block.input.get("command") or block.input.get("file_path") or ""
                    log.caption(f"Tool: {block.name} {detail}")
        elif isinstance(message, ResultMessage):
            result = message
    return result


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Skill Runner", page_icon="📄")
st.title("Skill Runner")

with st.sidebar:
    st.header("Settings")
    skill_path = st.text_input(
        "Skill folder path",
        value=st.session_state.get("skill_path", ""),
        placeholder="/Users/you/.claude/skills/my-skill",
        help="The folder that contains SKILL.md",
    )
    st.session_state["skill_path"] = skill_path

uploaded = st.file_uploader("Upload a PDF", type=["pdf"])
instructions = st.text_area("Instructions for the skill", height=120)

if st.button("Run", type="primary", disabled=not (uploaded and skill_path)):
    skill_dir = Path(skill_path).expanduser()
    if not (skill_dir / "SKILL.md").exists():
        st.error(f"No SKILL.md found in {skill_dir}")
        st.stop()

    run_dir, skill_name = prepare_workspace(skill_dir, uploaded)

    with st.status(f"Running /{skill_name}...", expanded=True) as status:
        try:
            result = asyncio.run(
                run_skill(run_dir, skill_name, uploaded.name, instructions, st.container())
            )
        except Exception as e:
            status.update(label="Run failed", state="error")
            st.error(str(e))
            st.stop()

        if result and result.subtype == "success":
            status.update(label="Done", state="complete", expanded=False)
        else:
            status.update(label="Agent did not finish cleanly", state="error")

    if result and result.result:
        st.markdown(result.result)
    if result and result.total_cost_usd is not None:
        st.caption(f"Cost: ${result.total_cost_usd:.4f}")

    # Collect PDFs the skill produced (prefer output/, fall back to anywhere new)
    pdfs = sorted((run_dir / "output").glob("*.pdf"))
    if not pdfs:
        pdfs = [p for p in run_dir.rglob("*.pdf") if "input" not in p.parts and ".claude" not in p.parts]

    st.session_state["outputs"] = [(p.name, p.read_bytes()) for p in pdfs]
    if not pdfs:
        st.warning(f"No output PDF found. Check the run folder: {run_dir}")

# Download buttons persist across Streamlit reruns via session_state
for name, data in st.session_state.get("outputs", []):
    st.download_button(f"Download {name}", data, file_name=name, mime="application/pdf")
