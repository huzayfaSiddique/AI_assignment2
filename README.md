# PUCIT BS (CS) GPA/CGPA Guider — Assignment 3

An intelligent, stateful GPA & CGPA assistant for PUCIT Computer Science students built with **LangGraph**, **FastMCP**, **SQLite Checkpointing**, and **Token Streaming**.

---

## 🚀 Submission Information

- **Student Name:** Huzayfa Siddique
- **Roll Number:** BCSF24M049
- **Live Hosted MCP Server URL:** `https://your-server.onrender.com/mcp` *(Replace with your deployed URL)*
- **MCP Server API Key:** *(None / or add your key if authentication is enabled)*
- **GitHub Repository (Server Code):** `https://github.com/your-username/pucit-gpa-mcp-server`

---

## 🛠 Features

1. **Model Context Protocol (MCP) Server ([server/](file:///home/huzayfa/BCSF24M049_Assignment_03/server/))**:
   - Built using `FastMCP` exposing all 7 GPA tools (`marks_to_grade_points`, `calculate_semester_gpa`, `calculate_new_cgpa`, `required_gpa_for_target`, `get_semester_courses`, `get_remaining_credit_hours`, `save_report`).
   - Accessible over HTTP at `/mcp` by any MCP client.

2. **Persistent Conversation Memory (SQLite Checkpointer)**:
   - Uses `AsyncSqliteSaver` connected to `chats.sqlite`.
   - Each conversation is tracked under a `thread_id` (student name).
   - Only the latest user message is transmitted per turn; LangGraph automatically manages prior message history with `add_messages`.
   - Supports `/history`, `/switch <name>`, and `/forget`.

3. **Real-time Token Streaming**:
   - Uses `app.astream(..., stream_mode=["updates", "messages"], version="v2")` to stream tokens live as the model generates them.

4. **Fault-Tolerant Offline Recovery**:
   - `ToolNode(handle_tool_errors=...)` captures server drops without crashing.
   - Automatically repairs dangling tool calls from interrupted sessions on thread load so conversations never get stuck.

5. **Dual Interface**:
   - **CLI**: Interactive terminal with slash commands (`python agent.py`).
   - **GUI**: Streamlit web application (`streamlit run app.py`).

---

## 💻 Local Setup & Execution

### 1. Install Dependencies
```bash
uv sync
# or with pip:
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)
Copy `.env.example` to `.env`:
```env
OMNIROUTE_BASE_URL=http://localhost:20128/v1
OMNIROUTE_API_KEY=your_key_here
OMNIROUTE_MODEL=auto

MCP_URL=http://127.0.0.1:8000/mcp
```

### 3. Start FastMCP Server (Terminal 1)
```bash
uv run python server/server.py
```
*(Serves tools on `http://127.0.0.1:8000/mcp`)*

### 4. Run the Agent (Terminal 2)

**Terminal CLI:**
```bash
uv run python agent.py
```
Commands in CLI:
- `/history` — View conversation history for active student
- `/switch` — Switch to another student profile
- `/forget` — Delete active student's conversation memory
- `quit` — Exit

**Streamlit Web GUI:**
```bash
uv run streamlit run app.py
```
*(Open `http://localhost:8501` in your browser)*
