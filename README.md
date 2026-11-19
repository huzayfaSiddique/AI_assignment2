# PUCIT GPA/CGPA Agent

1. Create and activate a virtual environment: `python -m venv venv`, then `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (macOS/Linux).
2. Install the dependencies: `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and add your OmniRoute configuration: `OMNIROUTE_API_KEY=your_key_here` (and optionally adjust `OMNIROUTE_BASE_URL` or `OMNIROUTE_MODEL`).
4. Chat in the terminal with `python agent.py` (type `quit` to exit), or run the GUI with `streamlit run app.py`.
5. Nothing is stored between runs; say "save this" in the conversation and the agent will write a report file.