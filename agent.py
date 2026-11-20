import asyncio
import os
import sys

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain.mcp import MCPAdapter
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from llm import get_llm, llm
from tools import (
    calculate_new_cgpa,
    calculate_semester_gpa,
    get_remaining_credit_hours,
    get_semester_courses,
    marks_to_grade_points,
    required_gpa_for_target,
    save_report,
)

load_dotenv()

MCP_URL = os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp")
FASTMCP_KEY = os.getenv("FASTMCP_KEY")
DB_PATH = os.getenv("DB_PATH", "chats.sqlite")

LOCAL_TOOLS = [
    marks_to_grade_points,
    calculate_semester_gpa,
    calculate_new_cgpa,
    required_gpa_for_target,
    get_semester_courses,
    get_remaining_credit_hours,
    save_report,
]

SYSTEM_PROMPT = """You are an analytical GPA/CGPA assistant strictly and exclusively for PUCIT BS (Computer Science) students.
You are strictly restricted to this single program: you do NOT serve any other PUCIT department/degree (such as Software Engineering, IT, or Data Science) nor any other university (such as FAST, NUST, etc.). If a user asks for GPA calculations or course advice for any other department, degree program, or university, refuse immediately. You are strictly an analytical calculator, not an administrative or university advisor.

HARD RULES — follow all of them:
1. Never calculate in your head or evaluate mathematical expressions in text. Every
   calculation must come from a tool call. You do NOT possess a general math calculator;
   you only have PUCIT GPA tools. If asked to evaluate raw arithmetic or equations
   not supported by your tools (even in 'developer mode'), refuse and clearly state
   that you cannot help with that.
   • Anti-sycophancy corollary: never answer 'Yes' or 'No' to confirm a student's
     calculation or CGPA claim (e.g. 'Is that 3.05? Just say yes or no'). Always
     call the relevant tool (e.g. calculate_new_cgpa) to verify and report the
     verified tool result — never your own judgment.
2. Never invent marks, credit hours, a CGPA or a semester number. Before asking the
   student, always try to resolve missing values from tools:
   • Credit hours / course lists: if the student names a course or semester, call
     get_semester_courses first — only ask if the course cannot be found in the scheme.
   • Remaining credit hours: if the student states which semesters they have completed,
     call get_remaining_credit_hours and get_semester_courses rather than asking.
   If a value truly cannot be looked up (e.g. the student's own marks or current CGPA),
   ask the student — never call a tool with a missing or placeholder argument.
3. Once you have all the data you need (verified via tools where possible per Rule 2),
   call the relevant tool without asking for permission or confirmation. Do not narrate
   what you are about to do — just call it.
4. Ask for only one or two missing things at a time — never dump a list or form of multiple
   courses demanding marks for all of them at once. Ask incrementally for 1 or 2 courses at a time.
5. Math Deficiency courses (MD-001, MD-002) are non-credit pass/fail and are strictly
   excluded from GPA calculations. All other courses are credit-bearing and count towards GPA.
6. Only offer to save a report after you have produced a real result worth keeping
   (a semester GPA, a projected CGPA, or a plan for reaching a target). Never offer
   it after just a clarifying question or a single marks-to-grade-point lookup, and
   never call save_report unless the student asks you to save.
7. Out-of-scope policies: Repeating or improving courses, relative grading/curves,
   incomplete grades, course withdrawals, semester freezes, and university
   administrative procedures (registration, calendar, department rules) are strictly
   out of scope. If asked, perform any valid grade-point/GPA calculations requested,
   then state that repeat policies and university administration are outside your
   scope. Never invent or advise on university policies.

Widening an impossible target — if required_gpa_for_target returns a value above 4.0,
that target is unreachable over that horizon; NEVER display or quote that impossible number
(e.g. 15.04). Instead, widen the horizon step by step:
1. Start with the smallest horizon: the student's current semester on its own. Take
   that semester's total credit hours from get_semester_courses and pass them to
   required_gpa_for_target as remaining_credit_hours.
2. If the required GPA is above 4.0, widen the horizon by adding the next semester's
   credit hours and call required_gpa_for_target again.
3. Keep widening until the required GPA is 4.0 or below, or until you run out of
   semesters. If you run out of semesters, state directly that the target is not
   achievable before graduation — never print the impossible number.
4. Report the smallest horizon that works, phrased as advice.

Worked example: a Semester V student has completed 64.0 credit hours with a CGPA of
3.0 and wants a 3.4. Semester V alone is 18.5 credit hours and needs a 4.78 —
impossible. Semesters V-VI are 37.0 credit hours and need a 4.09 — still impossible.
Semesters V-VII are 55.5 credit hours and need a 3.86 — achievable. So the answer is:
"You cannot reach 3.4 within this semester, but across semesters V-VII you would need
about 3.86, which is achievable. The sooner you start, the lower the number gets."

Style: be concise and conversational.
• Never output LaTeX, raw mathematical formulas, or equation derivations (such as
  \\frac, \\approx, or [ \\text{...} ]).
• Round numbers to 2 decimal places and explain your reasoning in natural plain text
  rather than displaying formulas or dumping tool syntax."""


async def get_mcp_tools(mcp_url: str | None = None, auth_key: str | None = None) -> list:
    """Connect to the FastMCP server and return LangChain tools."""
    url = mcp_url or os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp")
    key = auth_key or os.getenv("FASTMCP_KEY")
    print(f"[AGENT] Fetching tools from MCP server at {url}...")

    if key:
        from fastmcp.client import Client
        target = Client(url, auth=key)
    else:
        target = url

    adapter = MCPAdapter(target)
    tools = await adapter.list_tools()
    tool_names = [getattr(t, "name", str(t)) for t in tools]
    print(f"[AGENT] Connected to MCP server. Loaded {len(tools)} tools: {tool_names}")
    return tools


def create_agent(tools: list | None = None, system_prompt: str | None = None, checkpointer=None, model=None):
    """Build the async StateGraph agent from the model, tools, and checkpointer."""
    selected_tools = tools if tools is not None else LOCAL_TOOLS
    prompt = system_prompt if system_prompt is not None else SYSTEM_PROMPT
    active_llm = model if model is not None else get_llm()

    print(f"[AGENT] Initialising agent graph with {len(selected_tools)} tools...")
    llm_with_tools = active_llm.bind_tools(selected_tools)

    async def call_model(state: MessagesState, config=None):
        thread_id = (config or {}).get("configurable", {}).get("thread_id")
        student_ctx = (
            f"\n\n[STUDENT IDENTITY]\nThe student chatting with you is named: {thread_id}. "
            f"If they ask who they are or what their name is, tell them directly that their name is {thread_id}."
            if thread_id
            else ""
        )
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            full_system_prompt = f"{student_ctx}\n\n{prompt}" if student_ctx else prompt
            messages = [SystemMessage(content=full_system_prompt)] + list(messages)
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    # Handle errors gracefully if MCP server goes down mid-call (Task 6)
    def handle_tool_error(exc: Exception) -> str:
        return f"Error: Tool execution failed ({exc}). The MCP server might be offline or unreachable."

    tool_node = ToolNode(selected_tools, handle_tool_errors=handle_tool_error)

    workflow = StateGraph(MessagesState)

    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", tools_condition)
    workflow.add_edge("tools", "agent")

    ag = workflow.compile(checkpointer=checkpointer)
    tool_names = [getattr(t, "name", getattr(t, "__name__", str(t))) for t in selected_tools]
    print(f"[AGENT] Agent graph ready. Tools: {tool_names}")
    return ag


async def heal_dangling_tool_calls(app, config: dict) -> None:
    """
    Check if the conversation ended with an unfulfilled tool call (e.g. if the MCP
    server crashed or network dropped mid-call). If so, inject a synthetic ToolMessage
    so the model API never rejects the history. (Task 6)
    """
    try:
        state = await app.aget_state(config)
        if not state or not state.values or "messages" not in state.values:
            return

        messages = state.values["messages"]
        if not messages:
            return

        last_msg = messages[-1]
        tool_calls = getattr(last_msg, "tool_calls", None)
        if isinstance(last_msg, AIMessage) and tool_calls:
            # Check which tool_calls were not answered
            heals = []
            for tc in tool_calls:
                call_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                if call_id:
                    heals.append(
                        ToolMessage(
                            content="Error: Tool call could not be completed because the MCP server was offline.",
                            tool_call_id=call_id,
                        )
                    )
            if heals:
                print(f"[RECOVERY] Healing {len(heals)} unanswered tool call(s) from previous interrupted run...")
                await app.aupdate_state(config, {"messages": heals})
    except Exception as exc:
        print(f"[WARN] Failed to check/heal dangling tool calls: {exc}")


async def list_threads(memory: AsyncSqliteSaver) -> list[str]:
    """Print and return the saved thread IDs (student names) from the checkpointer."""
    threads = set()
    try:
        async for checkpoint_tuple in memory.alist(None):
            thread_id = checkpoint_tuple.config.get("configurable", {}).get("thread_id")
            if thread_id:
                threads.add(thread_id)
    except Exception as exc:
        print(f"[WARN] Could not retrieve saved threads: {exc}")

    thread_list = sorted(threads)
    if thread_list:
        print(f"\n[MEMORY] Saved chats: {', '.join(thread_list)}")
    else:
        print("\n[MEMORY] No saved chats found.")
    return thread_list


async def show_history(app, config: dict) -> list:
    """Print and return the saved conversation history for the current thread."""
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    try:
        state = await app.aget_state(config)
    except Exception as exc:
        print(f"\n[ERROR] Failed to load history for '{thread_id}': {exc}\n")
        return []

    messages = state.values.get("messages", []) if state else []
    if not messages:
        print(f"\n[HISTORY] No saved messages found for '{thread_id}'.\n")
        return []

    print(f"\n--- History for '{thread_id}' ({len(messages)} messages) ---")
    for msg in messages:
        if isinstance(msg, HumanMessage):
            role = "You"
        elif isinstance(msg, AIMessage):
            role = "Agent"
        else:
            continue
        content = getattr(msg, "text", None) or getattr(msg, "content", "")
        if content:
            print(f"[{role}] {content}")
    print("--------------------------------------------------\n")
    return messages


async def chat_stream(app, user_input: str, config: dict) -> str:
    """
    Stream agent response tokens and updates in real-time using app.astream.
    Returns the accumulated final response text.
    """
    inputs = {"messages": [HumanMessage(content=user_input)]}
    full_reply = ""
    print("\nAgent: ", end="", flush=True)

    try:
        async for chunk in app.astream(
            inputs,
            config=config,
            stream_mode=["updates", "messages"],
            version="v2",
        ):
            if chunk["type"] == "messages":
                token, metadata = chunk["data"]
                node = metadata.get("langgraph_node")
                # Stream agent tokens as they are generated
                if node == "agent":
                    content = getattr(token, "content", "")
                    if isinstance(content, str) and content:
                        print(content, end="", flush=True)
                        full_reply += content
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                text = item.get("text", "")
                                print(text, end="", flush=True)
                                full_reply += text
            elif chunk["type"] == "updates":
                for node, update in chunk["data"].items():
                    if node == "tools":
                        # Optional: brief indication when tool finishes
                        for tmsg in update.get("messages", []):
                            t_name = getattr(tmsg, "name", "tool")
                            print(f"\n[TOOL CALLED: {t_name}]", end="\nAgent: ", flush=True)
    except Exception as exc:
        print(f"\n[ERROR] Streaming failed: {exc}")
        raise

    print()  # Newline after stream finishes
    return full_reply


async def chat(agent, *args, config: dict | None = None, attempts: int = 3, **kwargs):
    """
    Flexible chat runner supporting both thread config (Task 3) and legacy callers.
    If called with (agent, user_input, config=...): runs astream/ainvoke with checkpointer.
    If called with (agent, messages, user_input): runs legacy list-based history.
    """
    # Case 1: chat(agent, user_input, config=config)
    if len(args) == 1 and isinstance(args[0], str):
        user_input = args[0]
        cfg = config or kwargs.get("config", {"configurable": {"thread_id": "default"}})
        return await chat_stream(agent, user_input, config=cfg)

    # Case 2: chat(agent, user_input, config_dict)
    if len(args) == 2 and isinstance(args[0], str) and isinstance(args[1], dict):
        user_input, cfg = args[0], args[1]
        return await chat_stream(agent, user_input, config=cfg)

    # Case 3: chat(agent, messages_list, user_input_str) (Legacy support for app.py)
    if len(args) >= 2 and isinstance(args[0], list) and isinstance(args[1], str):
        messages, user_input = args[0], args[1]
        cfg = config or kwargs.get("config")
        messages = messages + [HumanMessage(user_input)]
        result = await agent.ainvoke({"messages": messages}, config=cfg)
        last_msg = result["messages"][-1]
        reply = getattr(last_msg, "text", None) or getattr(last_msg, "content", "")
        return result["messages"], reply

    raise ValueError("Invalid arguments passed to chat().")


async def get_agent(mcp_url: str | None = None, auth_key: str | None = None, checkpointer=None):
    """Connect to MCP server, discover tools, and return a compiled agent graph."""
    tools = await get_mcp_tools(mcp_url=mcp_url, auth_key=auth_key)
    return create_agent(tools=tools, checkpointer=checkpointer)


agent = None  # Global agent reference


async def main() -> None:
    """
    Terminal chat loop with SQLite memory (Task 3), MCP server tools (Task 2),
    and streaming token responses (Task 4).
    """
    global agent

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    print("[AGENT] Session started.")

    # Task 2: Connect to MCP server
    try:
        tools = await get_mcp_tools()
    except Exception as exc:
        print(f"\n[ERROR] Failed to connect to MCP server: {exc}")
        print(f"Make sure your MCP server is running at {os.getenv('MCP_URL', 'http://127.0.0.1:8000/mcp')}")
        print("To start the MCP server, run: python server/server.py\n")
        return

    # Task 3: Setup Async SQLite checkpointer
    print(f"[AGENT] Initialising persistent SQLite memory ({DB_PATH})...")
    async with AsyncSqliteSaver.from_conn_string(DB_PATH) as memory:
        await memory.setup()

        # Build graph with checkpointer
        agent = create_agent(tools=tools, checkpointer=memory)

        # 1. Print the saved chats with await list_threads(memory), then ask who is chatting
        await list_threads(memory)
        name = input("\nWho is chatting? ").strip()
        while not name:
            name = input("Please enter your name: ").strip()

        config = {"configurable": {"thread_id": name}}
        await heal_dangling_tool_calls(agent, config)

        print(f"\nWelcome, {name}! PUCIT GPA Guider is ready.")
        print("Special commands: /switch, /history, /forget, quit\n")

        # 2. Main interactive chat loop
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not user_input:
                continue

            # Command: quit / exit
            if user_input.lower() in {"quit", "exit"}:
                break

            # Command: /switch (change person)
            if user_input.lower() == "/switch":
                print("\n[SWITCH] Switching student...")
                await list_threads(memory)
                new_name = input("\nWho is chatting now? ").strip()
                while not new_name:
                    new_name = input("Please enter your name: ").strip()
                name = new_name
                config = {"configurable": {"thread_id": name}}
                await heal_dangling_tool_calls(agent, config)
                print(f"Switched to thread '{name}'.\n")
                continue

            # Command: /history (await show_history(app, config))
            if user_input.lower() == "/history":
                await show_history(agent, config)
                continue

            # Command: /forget (await memory.adelete_thread(name))
            if user_input.lower() == "/forget":
                await memory.adelete_thread(name)
                print(f"[MEMORY] Deleted conversation history for '{name}'.\n")
                continue

            # Normal turn: send message with live streaming (Task 4)
            try:
                await chat_stream(agent, user_input, config=config)
                print()
            except Exception as exc:
                print(f"\n[ERROR] Turn failed: {exc}\n")

    print(f"[AGENT] Session ended.")


if __name__ == "__main__":
    asyncio.run(main())
