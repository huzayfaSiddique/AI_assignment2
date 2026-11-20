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


# Initialize session state for student name (empty by default)
if "student_name" not in st.session_state:
    st.session_state.student_name = ""

# Sidebar: student / thread configuration
with st.sidebar:
    st.header("Student Profile")

    name_input = st.text_input(
        "Your Name (Thread ID)",
        value=st.session_state.student_name,
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
            async def _delete():
                async with AsyncSqliteSaver.from_conn_string(DB_PATH) as memory:
                    await memory.setup()
                    await memory.adelete_thread(student_name)
            run_async(_delete())
            st.session_state.messages = []
            st.success(f"Deleted saved memory for '{student_name}'.")
            st.rerun()

    if st.button("View History (/history)", disabled=not student_name):
        saved = run_async(_load_saved_messages(student_name))
        if saved:
            st.session_state.messages = saved
            st.rerun()
        else:
            st.info(f"No history found for '{student_name}'.")

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

# Chat input: disabled if thread ID is not set
if not student_name:
    st.chat_input("Please enter your Name (Thread ID) in the sidebar first...", disabled=True)
else:
    if prompt := st.chat_input("Ask a question, or type /history, /switch <name>, /forget"):
        cmd = prompt.strip()

        # 1. Command: /history
        if cmd.lower() == "/history":
            saved_msgs = run_async(_load_saved_messages(student_name))
            with st.chat_message("user"):
                st.markdown("`/history`")
            with st.chat_message("assistant"):
                if not saved_msgs:
                    msg_text = f"No saved history found for '{student_name}'."
                    st.info(msg_text)
                else:
                    msg_text = f"### 📜 Saved History for '{student_name}' ({len(saved_msgs)} messages)\n\n"
                    for m in saved_msgs:
                        role = "You" if isinstance(m, HumanMessage) else "Agent"
                        content = getattr(m, "text", None) or getattr(m, "content", "")
                        if content:
                            msg_text += f"- **{role}**: {content}\n\n"
                    st.markdown(msg_text)
            st.session_state.messages.append(HumanMessage(content="/history"))
            st.session_state.messages.append(AIMessage(content=msg_text))
            st.stop()

        # 2. Command: /forget
        if cmd.lower() == "/forget":
            async def _delete_thread():
                async with AsyncSqliteSaver.from_conn_string(DB_PATH) as memory:
                    await memory.setup()
                    await memory.adelete_thread(student_name)
            run_async(_delete_thread())
            st.session_state.messages = []
            st.toast(f"Deleted memory for '{student_name}'", icon="🗑️")
            st.success(f"Conversation memory for '{student_name}' has been forgotten.")
            st.rerun()

        # 3. Command: /switch
        if cmd.lower().startswith("/switch"):
            parts = cmd.split(maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                new_target = parts[1].strip()
                st.session_state.student_name = new_target
                st.session_state.active_thread = new_target
                st.session_state.messages = run_async(_load_saved_messages(new_target))
                st.toast(f"Switched to {new_target}", icon="🔄")
                st.rerun()
            else:
                with st.chat_message("user"):
                    st.markdown(cmd)
                with st.chat_message("assistant"):
                    st.info("To switch students, type `/switch <name>` (e.g. `/switch Bilal`) or change the name in the sidebar.")
                st.stop()

        # Normal turn: send message to agent
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append(HumanMessage(content=prompt))

        with st.chat_message("assistant"):
            with st.spinner("Working it out..."):
                try:
                    async def _run_turn():
                        async with AsyncSqliteSaver.from_conn_string(DB_PATH) as memory:
                            await memory.setup()
                            tools = await get_mcp_tools()
                            app = create_agent(tools=tools, checkpointer=memory)
                            await heal_dangling_tool_calls(app, config)
                            result = await app.ainvoke(
                                {"messages": [HumanMessage(content=prompt)]},
                                config=config,
                            )
                            last_msg = result["messages"][-1]
                            return getattr(last_msg, "text", None) or getattr(last_msg, "content", "")

                    reply = run_async(_run_turn())
                    st.session_state.messages.append(AIMessage(content=reply))
                    st.markdown(reply)
                except Exception as exc:
                    st.error(f"Could not complete that turn: {exc}")
