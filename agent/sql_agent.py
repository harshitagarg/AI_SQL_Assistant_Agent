from dotenv import load_dotenv
import streamlit as st
import sqlite3
import os
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain.agents import create_agent
from config import LLM_PROVIDER, GROQ_MODEL, GEMINI_MODEL


load_dotenv()

_agent_cache = {}  # cache agents per db_path

def get_tools(db_path: str):
    """Returns tools bound to a specific DB file."""
    
    @tool
    def sql_db_list_tables() -> str:
        """Input is an empty string, output is a comma-separated list of tables in the database."""
        con = sqlite3.connect(db_path)
        try:
            cursor = con.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]
            return ", ".join(tables)
        finally:
            con.close()

    @tool
    def sql_db_schema(table_names: str) -> str:
        """Input to this tool is a comma-separated list of tables, output is the schema and sample rows for those tables.
        Be sure that the tables actually exist by calling sql_db_list_tables first!
        Example Input: table1, table2, table3"""
        con = sqlite3.connect(db_path)
        try:
            cursor = con.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            valid_tables = {row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")}
            results = []
            for table in table_names.split(","):
                table = table.strip()
                if table not in valid_tables:
                    results.append(f"Error: table_names {{{table!r}}} not found in database")
                    continue
                cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?;", (table,))
                schema_row = cursor.fetchone()
                if schema_row:
                    results.append(schema_row[0])
                    try:
                        quoted_table = '"' + table.replace('"', '""') + '"'
                        cursor.execute(f"SELECT * FROM {quoted_table} LIMIT 3;")
                        rows = cursor.fetchall()
                        if rows:
                            col_names = [description[0] for description in cursor.description]
                            results.append(f"/*\n3 rows from {table} table:\n" + "\t".join(col_names) + "\n" + "\n".join("\t".join(str(x) for x in row) for row in rows) + "\n*/")
                    except Exception as e:
                        results.append(f"Error fetching sample rows: {e}")
            return "\n\n".join(results)
        finally:
            con.close()

    @tool
    def sql_db_query(query: str) -> str:
        """Input to this tool is a detailed and correct SQL query, output is a result from the database.
        If the query is not correct, an error message will be returned.
        If an error is returned, rewrite the query, check the query, and try again.
        If you encounter an issue with Unknown column 'xxxx' in 'field list', use sql_db_schema to query the correct table fields."""
        con = sqlite3.connect(db_path)
        try:
            cursor = con.cursor()
            cursor.execute(query)
            res = cursor.fetchall()
            return str(res)
        except Exception as e:
            return f"Error: {e}"
        finally:
            con.close()

    @tool
    def sql_db_query_checker(query: str) -> str:
        """Use this tool to double check if your query is correct before executing it.
        Always use this tool before executing a query with sql_db_query!"""
        trigger_prompt = """{query}
    Double check the sqlite query above for common mistakes, including:
    - Using NOT IN with NULL values
    - Using UNION when UNION ALL should have been used
    - Using BETWEEN for exclusive ranges
    - Data type mismatch in predicates
    - Properly quoting identifiers
    - Using the correct number of arguments for functions
    - Casting to the correct data type
    - Using the proper columns for joins

    If there are any of the above mistakes, rewrite the query. If there are no mistakes, just reproduce the original query.

    Output the final SQL query only.

    SQL Query: """.format(query=query)

        response = model.invoke(trigger_prompt)
        return response.content.strip()
    
    return [sql_db_list_tables, sql_db_schema, sql_db_query]


# ── Agent ──────────────────────────────────────────────────────────────

def get_agent(db_path: str, system_prompt: str):
    """Returns cached agent for a given DB, or creates new one."""
    if db_path not in _agent_cache:
        if LLM_PROVIDER == "groq":
            from langchain_groq import ChatGroq
            model = ChatGroq(model=GROQ_MODEL, temperature=0)
        else:
            model = init_chat_model(GEMINI_MODEL)
        tools = get_tools(db_path)
        _agent_cache[db_path] = create_agent(
            model, tools, system_prompt=system_prompt, debug=False
        )
    return _agent_cache[db_path]

# ── Runner (returns final answer + trace steps) ────────────────────────

def run_agent(question: str, db_path: str, system_prompt: str, chat_history: list) -> dict:
    """
    Runs agent with full chat history for multi-turn conversation.
    Returns {"answer": str, "steps": list}
    """
    agent = get_agent(db_path, system_prompt)

    # Build messages with history
    messages = []
    for turn in chat_history:
        messages.append({"role": "user", "content": turn["question"]})
        messages.append({"role": "assistant", "content": turn["answer"]})
    messages.append({"role": "user", "content": question})

    seen_ids = set()
    steps = []
    final_answer = ""
    last_tool_result = ""  # fallback if model doesn't produce final text
    for step in agent.stream(
        {"messages": messages},
        stream_mode="updates",
    ):
        for node_output in step.values():
            for msg in node_output.get("messages", []):
                msg_id = getattr(msg, "id", None)
                if msg_id in seen_ids:
                    continue
                if msg_id:
                    seen_ids.add(msg_id)

                if isinstance(msg, AIMessage):
                    for tc in getattr(msg, "tool_calls", []):
                        args_str = ", ".join(f"{k}={v!r}" for k, v in tc["args"].items())
                        steps.append({"type": "tool_call", "name": tc["name"], "args": args_str})
                    if msg.content:
                        final_answer = msg.content
                        steps.append({"type": "answer", "content": msg.content})

                elif isinstance(msg, ToolMessage):
                    content = msg.content
                    last_tool_result = content  # save last tool result as fallback
                    if len(content) > 400:
                        content = content[:400] + "\n... [truncated]"
                    steps.append({"type": "tool_result", "content": content})

    # ── Fallback: if model returned no final text, format the raw result ──
    if not final_answer and last_tool_result:
        final_answer = f"Here are the query results:\n\n{last_tool_result}"
        steps.append({"type": "answer", "content": final_answer})

    return {"answer": final_answer, "steps": steps}
