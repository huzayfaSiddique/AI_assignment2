# PUCIT GPA/CGPA Agent

1. Create and activate a virtual environment: `python -m venv venv`, then `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (macOS/Linux).
2. Install the dependencies: `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and configure your API key (`OMNIROUTE_API_KEY=your_key_here`) and MCP server URL (`MCP_URL=http://127.0.0.1:8000/mcp`).
4. Start the MCP server: `python server/server.py` (serves tools on `http://127.0.0.1:8000/mcp`).
5. In another terminal, run the agent with `python agent.py` (type `quit` to exit), or run the GUI with `streamlit run app.py`.
5. Nothing is stored between runs; say "save this" in the conversation and the agent will write a report file.