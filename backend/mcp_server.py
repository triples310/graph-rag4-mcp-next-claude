# mcp_server.py
import base64
import re
import tempfile
from pathlib import Path
from fastmcp import FastMCP
import json

from build_graph import build_graph_for_user
from chatbot import get_chatbot_response, get_graph, is_graph_populated

mcp = FastMCP("GraphRAG Chatbot")

USER_DB_MAP: dict[str, str] = {}
USERS_FILE = Path("users.json")


def _db_for_user(username: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", username)
    # Lowercase and prefix
    db_name = "user" + cleaned.lower()
    return db_name

def _check_database_exists(db_name: str) -> bool:
    try:
        graph = get_graph(db_name)
        return is_graph_populated(graph)   # true only if graph has data
    except Exception:
        return False


# ========================= TOOL: UPLOAD =========================

@mcp.tool()
def upload_pdf(username: str, pdf_base64: str, filename: str = "upload.pdf") -> dict:
    try:
        # ✅ Fix base64 padding
        pdf_base64 = pdf_base64.strip()
        missing_padding = len(pdf_base64) % 4
        if missing_padding:
            pdf_base64 += "=" * (4 - missing_padding)

        pdf_bytes = base64.b64decode(pdf_base64, validate=False)

    except Exception as e:
        return {"status": "error", "message": f"Invalid base64: {e}"}

    tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        db_name = _db_for_user(username)

        result = build_graph_for_user(tmp_path, db_name)

        USER_DB_MAP[username] = db_name

        return {
            "status": "success",
            "database": db_name,
            "company": result.get("company"),
            "nodes_created": result.get("nodes_created"),
            "pages": result.get("pages"),
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


# ========================= TOOL: CHAT =========================

@mcp.tool()
def chat(username: str, question: str) -> dict:
    db_name = _db_for_user(username)
    answer = get_chatbot_response(question, db_name)
    return {"question": question, "answer": answer}


# ========================= TOOL: STATUS =========================

@mcp.tool()
def get_status(username: str) -> dict:
    db_name = _db_for_user(username)
    exists = _check_database_exists(db_name)
    return {
        "username": username,
        "database": db_name,
        "graph_exists": exists,
    }


# ========================= TOOL: BUILD LOCAL =========================

@mcp.tool()
def build_graph(username: str, pdf_path: str) -> dict:
    db_name = _db_for_user(username)
    result = build_graph_for_user(pdf_path, db_name)
    USER_DB_MAP[username] = db_name
    return result


# ========================= RUN =========================

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001, path="/mcp")