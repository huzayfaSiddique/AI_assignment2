import asyncio
import streamlit as st
from langchain.messages import AIMessage, HumanMessage

from agent import chat, get_agent
from tools import save_report

st.set_page_config(page_title="PUCIT GPA/CGPA Agent", page_icon="🎓")
st.title("PUCIT (COMPUTER SCIENCE) GPA/CGPA Agent")

# Initialize agent connected to MCP server
if "agent" not in st.session_state:
    try:
        with st.spinner("Connecting to MCP server..."):
            st.session_state.agent = asyncio.run(get_agent())
    except Exception as exc:
        st.error(
            f"Could not connect to MCP server: {exc}\n\n"
            "Please ensure the FastMCP server is running: `python server/server.py`"
        )
        st.stop()

agent = st.session_state.agent

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    if isinstance(message, HumanMessage):
        role, text = "user", message.text
    elif isinstance(message, AIMessage):
        role, text = "assistant", message.text
    else:
        continue
    if text:
        with st.chat_message(role):
            st.markdown(text)

if prompt := st.chat_input("e.g. I'm in semester 5 with a CGPA of 3.0 - what do I need for a 3.4?"):
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Working it out..."):
            try:
                st.session_state.messages, reply = asyncio.run(
                    chat(agent, st.session_state.messages, prompt)
                )
                st.markdown(reply)
            except Exception as exc:
                st.error(f"Could not complete that turn: {exc}")

with st.sidebar:
    st.header("Controls")
    if st.button("Reset conversation"):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.subheader("Save last report")
    filename = st.text_input("File name", value="gpa_report.txt")
    last_answer = next(
        (m.text for m in reversed(st.session_state.messages)
         if isinstance(m, AIMessage) and m.text),
        "",
    )
    if st.button("Save last report", disabled=not last_answer):
        result = save_report(filename, last_answer)
        if result.startswith("Saved"):
            st.success(result)
        else:
            st.error(result)

    st.divider()
    with st.expander("Example questions"):
        st.markdown(
            "- I got 78 in Analysis of Algorithms, 85 in AI and 64 in HCI. "
            "What's my GPA?\n"
            "- My CGPA is 3.1 and I've done 64 credit hours. If I get a 3.6 this "
            "semester, where do I end up?\n"
            "- I want to graduate with a 3.5. What do I need from here?\n"
            "- What courses are in semester 6?"
        )
