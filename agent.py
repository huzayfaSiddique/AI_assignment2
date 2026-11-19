import asyncio
import os
import sys

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.mcp import MCPAdapter
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from llm import llm
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


def create_agent(tools: list | None = None, system_prompt: str | None = None, checkpointer=None):
    """Build the async StateGraph agent from the model, tools, and system prompt."""
    selected_tools = tools if tools is not None else LOCAL_TOOLS
    prompt = system_prompt if system_prompt is not None else SYSTEM_PROMPT

    print(f"[AGENT] Initialising agent graph with {len(selected_tools)} tools...")
    llm_with_tools = llm.bind_tools(selected_tools)

    async def call_model(state: MessagesState):
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=prompt)] + list(messages)
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    workflow = StateGraph(MessagesState)

    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(selected_tools))

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", tools_condition)
    workflow.add_edge("tools", "agent")

    ag = workflow.compile(checkpointer=checkpointer)
    tool_names = [getattr(t, "name", getattr(t, "__name__", str(t))) for t in selected_tools]
    print(f"[AGENT] Agent graph ready. Tools: {tool_names}")
    return ag


async def get_agent(mcp_url: str | None = None, auth_key: str | None = None, checkpointer=None):
    """Connect to MCP server, discover tools, and return a compiled agent graph."""
    tools = await get_mcp_tools(mcp_url=mcp_url, auth_key=auth_key)
    return create_agent(tools=tools, checkpointer=checkpointer)


agent = None  # Populated when running or via get_agent()


async def chat(agent, messages, user_input: str, attempts: int = 3, config: dict | None = None):
    """
    Run one conversation turn asynchronously and return (messages, reply).

    The model is stateless, so the caller carries the history: pass in the whole
    `messages` list plus the new user input, and feed the returned list into the
    next call.
    """
    turn = len(messages) + 1
    print(f"\n[AGENT] Turn {turn} | User: {user_input[:120]}")
    messages = messages + [HumanMessage(user_input)]
    for attempt in range(1, attempts + 1):
        try:
            print(f"[AGENT] Invoking agent (attempt {attempt}/{attempts})...")
            result = await agent.ainvoke({"messages": messages}, config=config)
            last_msg = result["messages"][-1]
            reply = getattr(last_msg, "text", None) or getattr(last_msg, "content", "")
            print(f"[AGENT] Reply: {reply[:120]}")
            return result["messages"], reply
        except Exception as exc:
            print(f"[WARN]  Attempt {attempt}/{attempts} failed: {exc}")
            if attempt == attempts:
                raise


async def main() -> None:
    """Terminal chat loop connecting to the MCP server."""
    global agent

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    print("[AGENT] Session started.")
    try:
        agent = await get_agent()
    except Exception as exc:
        print(f"\n[ERROR] Failed to connect to MCP server: {exc}")
        print(f"Make sure your MCP server is running at {os.getenv('MCP_URL', 'http://127.0.0.1:8000/mcp')}")
        print("To start the MCP server, run: python server/server.py\n")
        return

    messages = []
    print("PUCIT GPA/CGPA agent (MCP connected). Ask a question, or type 'quit' to exit.\n")
    while True:
        try:
            user_input = input("You: ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if user_input.strip().lower() in {"quit", "exit"}:
            break
        if not user_input.strip():
            continue
        try:
            messages, reply = await chat(agent, messages, user_input)
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] Turn failed: {exc}\n")
            continue
        print(f"Agent: {reply}\n")
    print(f"[AGENT] Session ended. Total turns: {len(messages) // 2}")


if __name__ == "__main__":
    asyncio.run(main())
