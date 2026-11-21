import asyncio
import os
import streamlit as st
from langchain.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

import agent
import importlib
importlib.reload(agent)
from agent import create_agent, get_mcp_tools, heal_dangling_tool_calls
from tools import save_report

st.set_page_config(page_title="PUCIT GPA/CGPA Agent", page_icon="🎓")
st.title("PUCIT (COMPUTER SCIENCE) GPA/CGPA Agent")

DB_PATH = os.getenv("DB_PATH", "chats.sqlite")

# Persistent loop runner for Streamlit to prevent "Event loop is closed" errors
_loop = None

def run_async(coro):
    global _loop
    try:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_loop)
        return _loop.run_until_complete(coro)
    except RuntimeError:
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        return _loop.run_until_complete(coro)


async def _load_saved_messages(name: str):
    if not name:
        return []
    try:
        async with AsyncSqliteSaver.from_conn_string(DB_PATH) as memory:
            await memory.setup()
            tools = await get_mcp_tools()
            app = create_agent(tools=tools, checkpointer=memory)
            cfg = {"configurable": {"thread_id": name}}
            await heal_dangling_tool_calls(app, cfg)
            state = await app.aget_state(cfg)
            if state and state.values and "messages" in state.values:
                return state.values["messages"]
    except Exception:
        pass
    return []


def _get_saved_thread_ids() -> list[str]:
    """Retrieve all distinct thread IDs stored in SQLite memory."""
    import sqlite3
    if not os.path.exists(DB_PATH):
        return []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id IS NOT NULL AND thread_id != ''"
            )
            rows = cursor.fetchall()
            threads = sorted(list(set(r[0] for r in rows if r[0])))
            return threads
    except Exception:
        return []


def _format_history_summary(name: str, saved_msgs: list) -> str:
    """Format saved messages into a readable conversation history transcript."""
    if not saved_msgs:
        return f"No saved history found for '{name}'."
    msg_text = f"### Saved History for '{name}' ({len(saved_msgs)} messages)\n\n"
    for m in saved_msgs:
        role = "You" if isinstance(m, HumanMessage) else "Agent"
        content = getattr(m, "text", None) or getattr(m, "content", "")
        if content:
            msg_text += f"- **{role}**: {content}\n\n"
    return msg_text



# Handle deferred thread switch before widgets are instantiated
if "pending_thread_switch" in st.session_state:
    target_th = st.session_state.pop("pending_thread_switch")
    st.session_state["sidebar_name"] = target_th
    st.session_state["student_name"] = target_th
    st.session_state["active_thread"] = target_th
    st.session_state["messages"] = run_async(_load_saved_messages(target_th)) if target_th else []
    st.session_state["show_switch_selector"] = False
    if target_th:
        st.toast(f"Switched to {target_th}", icon="🔄")
    else:
        st.toast("Memory forgotten & session cleared", icon="🗑️")


# Initialize session state for student name (empty by default)
if "sidebar_name" not in st.session_state:
    st.session_state.sidebar_name = ""
if "student_name" not in st.session_state:
    st.session_state.student_name = ""
if "show_switch_selector" not in st.session_state:
    st.session_state.show_switch_selector = False


# Sidebar: student / thread configuration
with st.sidebar:
    st.header("Student Profile")

    name_input = st.text_input(
        "Your Name (Thread ID)",
        placeholder="Enter your name (e.g. Huzayfa)",
        key="sidebar_name",
    ).strip()
    st.session_state.student_name = name_input
    student_name = name_input

    config = {"configurable": {"thread_id": student_name}} if student_name else None

    # If student switched or newly entered, load their saved chat history from SQLite
    if student_name and st.session_state.get("active_thread") != student_name:
        st.session_state.active_thread = student_name
        saved_msgs = run_async(_load_saved_messages(student_name))
        st.session_state.messages = saved_msgs
    elif not student_name:
        st.session_state.active_thread = ""
        st.session_state.messages = []

    st.divider()
    st.header("Memory Controls")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("Clear UI"):
            st.session_state.messages = []
            st.rerun()

    with col_btn2:
        if st.button("Forget Me (/forget)", disabled=not student_name):
            target_to_forget = student_name
            async def _delete():
                async with AsyncSqliteSaver.from_conn_string(DB_PATH) as memory:
                    await memory.setup()
                    await memory.adelete_thread(target_to_forget)
            run_async(_delete())
            st.session_state["pending_thread_switch"] = ""
            st.rerun()


    col_btn3, col_btn4 = st.columns(2)
    with col_btn3:
        if st.button("History (/history)", disabled=not student_name):
            saved = run_async(_load_saved_messages(student_name))
            summary = _format_history_summary(student_name, saved)
            st.session_state.messages.append(HumanMessage(content="/history"))
            st.session_state.messages.append(AIMessage(content=summary))
            st.rerun()

    with col_btn4:
        if st.button("Switch (/switch)"):
            st.session_state.show_switch_selector = True
            st.rerun()



    st.divider()
    st.subheader("Save Last Report")
    filename = st.text_input("File name", value="gpa_report.txt")
    last_answer = next(
        (getattr(m, "text", None) or getattr(m, "content", "")
         for m in reversed(st.session_state.get("messages", []))
         if isinstance(m, AIMessage) and (getattr(m, "text", None) or getattr(m, "content", ""))),
        "",
    )
    if st.button("Save Report", disabled=not last_answer):
        result = save_report(filename, last_answer)
        if result.startswith("Saved"):
            st.success(result)
        else:
            st.error(result)

    st.divider()
    with st.expander("Commands & Shortcuts"):
        st.markdown(
            "- `/history` — Show saved SQLite history\n"
            "- `/switch <name>` — Switch to another student\n"
            "- `/forget` — Delete current student's memory\n"
        )

# Initialize messages
if "messages" not in st.session_state:
    st.session_state.messages = []

# When no thread ID is set yet, show an informational banner
if not student_name:
    st.info("👋 Welcome to the **PUCIT GPA/CGPA Guider**! Please enter your **Name (Thread ID)** in the sidebar on the left to start chatting.")

# Display conversation messages
for message in st.session_state.messages:
    if isinstance(message, HumanMessage):
        role = "user"
        text = getattr(message, "text", None) or getattr(message, "content", "")
    elif isinstance(message, AIMessage):
        role = "assistant"
        text = getattr(message, "text", None) or getattr(message, "content", "")
    else:
        continue
    if text:
        with st.chat_message(role):
            st.markdown(text)

# Interactive Session Switcher: displayed when /switch is entered or "Switch" button is pressed
if st.session_state.get("show_switch_selector"):
    with st.container(border=True):
        st.markdown("### 🔄 Switch Student Session")
        saved_threads = _get_saved_thread_ids()

        col_drop, col_new = st.columns([1, 1])
        with col_drop:
            if saved_threads:
                default_idx = (
                    saved_threads.index(student_name)
                    if student_name in saved_threads
                    else 0
                )
                selected_th = st.selectbox(
                    "Select an existing student session:",
                    options=saved_threads,
                    index=default_idx,
                    key="switch_thread_selector",
                )
            else:
                st.info("No saved student sessions in SQLite yet.")
                selected_th = ""

        with col_new:
            custom_name = st.text_input(
                "Or enter a new name to start fresh:",
                placeholder="e.g. Bilal, Ali",
                key="custom_switch_name",
            ).strip()

        target_to_switch = custom_name if custom_name else selected_th

        col_sw1, col_sw2 = st.columns([1, 4])
        with col_sw1:
            if st.button("Switch Session", type="primary", disabled=not target_to_switch):
                st.session_state["pending_thread_switch"] = target_to_switch
                st.session_state["show_switch_selector"] = False
                st.rerun()
        with col_sw2:
            if st.button("Cancel"):
                st.session_state.show_switch_selector = False
                st.rerun()

# Chat input: disabled if thread ID is not set
if not student_name:
    st.chat_input("Please enter your Name (Thread ID) in the sidebar first...", disabled=True)
else:
    if prompt := st.chat_input("Ask a question, or type /history, /switch, /forget"):
        cmd = prompt.strip()

        # 1. Command: /history
        if cmd.lower() == "/history":
            saved_msgs = run_async(_load_saved_messages(student_name))
            summary = _format_history_summary(student_name, saved_msgs)
            st.session_state.messages.append(HumanMessage(content="/history"))
            st.session_state.messages.append(AIMessage(content=summary))
            st.rerun()


        # 2. Command: /forget
        if cmd.lower() == "/forget":
            target_to_forget = student_name
            async def _delete_thread():
                async with AsyncSqliteSaver.from_conn_string(DB_PATH) as memory:
                    await memory.setup()
                    await memory.adelete_thread(target_to_forget)
            run_async(_delete_thread())
            st.session_state["pending_thread_switch"] = ""
            st.rerun()


        # 3. Command: /switch
        if cmd.lower().startswith("/switch"):
            parts = cmd.split(maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                new_target = parts[1].strip()
                st.session_state["pending_thread_switch"] = new_target
                st.session_state["show_switch_selector"] = False
                st.rerun()
            else:
                st.session_state.show_switch_selector = True
                st.rerun()



        # Normal turn: send message to agent
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append(HumanMessage(content=prompt))

        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("*(Thinking...)*")

            try:
                async def _run_stream():
                    async with AsyncSqliteSaver.from_conn_string(DB_PATH) as memory:
                        await memory.setup()
                        tools = await get_mcp_tools()
                        agent_app = create_agent(tools=tools, checkpointer=memory)
                        await heal_dangling_tool_calls(agent_app, config)

                        full_reply = ""
                        async for chunk in agent_app.astream(
                            {"messages": [HumanMessage(content=prompt)]},
                            config=config,
                            stream_mode=["updates", "messages"],
                            version="v2",
                        ):
                            if chunk["type"] == "messages":
                                token, metadata = chunk["data"]
                                node = metadata.get("langgraph_node")
                                if node == "agent":
                                    content = getattr(token, "content", "")
                                    if isinstance(content, str) and content:
                                        full_reply += content
                                        placeholder.markdown(full_reply + "▌")
                                    elif isinstance(content, list):
                                        for item in content:
                                            if isinstance(item, dict) and item.get("type") == "text":
                                                full_reply += item.get("text", "")
                                                placeholder.markdown(full_reply + "▌")
                            elif chunk["type"] == "updates":
                                for node, update in chunk["data"].items():
                                    if node == "tools":
                                        for tmsg in update.get("messages", []):
                                            t_name = getattr(tmsg, "name", "GPA tool")
                                            placeholder.markdown(f"⚙️ *Calculating with `{t_name}`...*\n\n")

                        placeholder.markdown(full_reply)
                        return full_reply

                reply = run_async(_run_stream())
                st.session_state.messages.append(AIMessage(content=reply))
            except Exception as exc:
                placeholder.error(f"Could not complete that turn: {exc}")

