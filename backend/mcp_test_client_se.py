"""
MCP Test Client for GraphRAG Chatbot Server
Usage:
    python mcp_test_client.py
    python mcp_test_client.py --username alice --question "what are the services?"
"""

import asyncio
import argparse
import json
import base64
from pathlib import Path

from mcp import ClientSession
from mcp.client.sse import sse_client


# ========================= CONFIG =========================

MCP_URL = "http://localhost:8001/sse"
MCP_API_KEY = ""  # Set this if you configured MCP_API_KEY on the server


def get_headers() -> dict:
    if MCP_API_KEY:
        return {"X-MCP-Key": MCP_API_KEY}
    return {}


# ========================= HELPERS =========================

def print_result(label: str, result):
    """Pretty-print a tool call result."""
    print(f"\n{'─'*50}")
    print(f"  {label}")
    print(f"{'─'*50}")
    if hasattr(result, "content"):
        for block in result.content:
            if hasattr(block, "text"):
                try:
                    parsed = json.loads(block.text)
                    print(json.dumps(parsed, indent=2))
                except json.JSONDecodeError:
                    print(block.text)
    else:
        print(result)


# ========================= TEST CASES =========================

async def test_list_tools(session: ClientSession):
    """
    Equivalent to:
        POST /messages/ {"method": "tools/list", "params": {}}
    """
    tools = await session.list_tools()
    print("\n📋 Available tools:")
    for tool in tools.tools:
        print(f"  • {tool.name}: {tool.description}")
    return tools


async def test_get_status(session: ClientSession, username: str):
    """
    Equivalent to:
        POST /messages/ {"method": "tools/call", "params": {"name": "get_status", "arguments": {"username": "..."}}}
    """
    result = await session.call_tool("get_status", {"username": username})
    print_result(f"get_status(username='{username}')", result)
    return result


async def test_chat(session: ClientSession, username: str, question: str):
    """
    Equivalent to:
        POST /messages/ {"method": "tools/call", "params": {"name": "chat", "arguments": {...}}}
    """
    result = await session.call_tool("chat", {
        "username": username,
        "question": question,
    })
    print_result(f"chat(username='{username}', question='{question}')", result)
    return result


async def test_upload_pdf(session: ClientSession, username: str, pdf_path: str):
    """
    Read a local PDF, encode it as base64, and upload via the MCP tool.
    Equivalent to the /upload-pdf endpoint in FastAPI but over MCP.
    """
    path = Path(pdf_path)
    if not path.exists():
        print(f"  ✗ PDF not found: {pdf_path}")
        return

    pdf_bytes = path.read_bytes()
    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    print(f"\n  Uploading {path.name} ({len(pdf_bytes):,} bytes)...")
    result = await session.call_tool("upload_pdf", {
        "username": username,
        "pdf_base64": pdf_b64,
        "filename": path.name,
    })
    print_result(f"upload_pdf(username='{username}', filename='{path.name}')", result)
    return result


# ========================= MAIN RUNNER =========================

async def run_tests(username: str, question: str, pdf_path: str | None):
    print(f"\n🔌 Connecting to MCP server at {MCP_URL}")

    async with sse_client(MCP_URL, headers=get_headers()) as (read, write):
        async with ClientSession(read, write) as session:
            # Handshake — the SDK does initialize + initialized for you
            await session.initialize()
            print("✅ Connected and initialized\n")

            # 1. List tools
            await test_list_tools(session)

            # 2. Check status
            await test_get_status(session, username)

            # 3. Upload PDF if provided
            if pdf_path:
                await test_upload_pdf(session, username, pdf_path)
                # Re-check status after upload
                await test_get_status(session, username)

            # 4. Chat
            await test_chat(session, username, question)


# ========================= CLI =========================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MCP GraphRAG test client")
    parser.add_argument("--username", default="alice", help="Username to test with")
    parser.add_argument("--question", default="what are the primary services?",
                        help="Question to ask the chatbot")
    parser.add_argument("--pdf", default=None,
                        help="Path to a PDF file to upload before chatting")
    args = parser.parse_args()

    asyncio.run(run_tests(
        username=args.username,
        question=args.question,
        pdf_path=args.pdf,
    ))