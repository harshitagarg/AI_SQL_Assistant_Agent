import streamlit as st
from agent.db_manager import load_file_to_db, get_db_info
from agent.sql_agent import run_agent
from agent.prompts import get_system_prompt

st.set_page_config(page_title="CSV SQL Agent", page_icon="🗄️", layout="wide")

# ── Sidebar — CSV Upload ───────────────────────────────────────────────
with st.sidebar:
    st.title("🗄️ CSV SQL Agent")
    st.caption("Upload a CSV, ask questions in plain English.")
    st.divider()

    uploaded_file = st.file_uploader("Upload your CSV or Excel file",
    type=["csv", "xlsx", "xls"]     
)

    if uploaded_file:
        if "db_path" not in st.session_state or st.session_state.get("filename") != uploaded_file.name:
            with st.spinner("Loading file into database..."):
                db_path, table_name, columns = load_file_to_db(uploaded_file)
                st.session_state.db_path = db_path
                st.session_state.table_name = table_name
                st.session_state.columns = columns
                st.session_state.system_prompt = get_system_prompt(table_name, columns)
                st.session_state.filename = uploaded_file.name
                st.session_state.chat_history = []  # reset on new file
            st.success(f"✅ Loaded: {uploaded_file.name}")

        # Show DB info
        if "db_path" in st.session_state:
            st.divider()
            st.markdown("**Database info**")
            db_info = get_db_info(st.session_state.db_path)
            for table, count in db_info.items():
                st.markdown(f"- `{table}`: {count:,} rows")
            st.divider()
            st.markdown("**Columns**")
            for col in st.session_state.columns:
                st.markdown(f"- `{col}`")

    if st.button("🗑️ Clear chat"):
        st.session_state.chat_history = []
        st.rerun()

# ── Main area ──────────────────────────────────────────────────────────
st.title("Ask your data anything")

if "db_path" not in st.session_state:
    st.info("👈 Upload a CSV file from the sidebar to get started.")
    st.stop()

# Initialize chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Display chat history
for turn in st.session_state.chat_history:
    with st.chat_message("user"):
        st.write(turn["question"])
    with st.chat_message("assistant"):
        st.write(turn["answer"])
        if turn.get("steps"):
            with st.expander("🔍 Agent reasoning"):
                for step in turn["steps"]:
                    if step["type"] == "tool_call":
                        st.code(f"{step['name']}({step['args']})", language="sql")
                    elif step["type"] == "tool_result":
                        st.text(step["content"])

# Chat input
question = st.chat_input("e.g. What are the top 5 best selling products?")

if question:
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = run_agent(
                question,
                st.session_state.db_path,
                st.session_state.system_prompt,
                st.session_state.chat_history,
            )
        st.write(result["answer"])
        with st.expander("🔍 Agent reasoning"):
            for step in result["steps"]:
                if step["type"] == "tool_call":
                    st.code(f"{step['name']}({step['args']})", language="sql")
                elif step["type"] == "tool_result":
                    st.text(step["content"])

    # Save to history
    st.session_state.chat_history.append({
        "question": question,
        "answer": result["answer"],
        "steps": result["steps"],
    })