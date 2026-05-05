"""
MCP Client to test the GraphRAG Chatbot server (streamable HTTP)
Usage:
    python test_mcp_client.py [--pdf path/to/file.pdf]
"""
import asyncio
import base64
import sys
from pathlib import Path
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

SERVER_URL = "http://localhost:8001/mcp"

# Sample test parameters
USERNAME = "Deep brown"
QUESTION = "What is the mission?"
PDF_PATH = "company_overview.pdf"  # default, override with --pdf


def encode_pdf(path: str) -> str:
    """Read a PDF file and return a base64 string (one line)."""
    data = Path(path).read_bytes()
    return base64.b64encode(data).decode("ascii")


async def main():
    # Allow overriding PDF path from command line
    pdf_path = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--pdf" else PDF_PATH

    print(f"🔗 Connecting to {SERVER_URL} ...")
    async with streamable_http_client(SERVER_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            # 1. Initialize (handshake + session ID automatically managed)
            await session.initialize()
            print("✅ Session initialized.\n")

            # 2. Test: get_status BEFORE upload
            print("📊 get_status (before upload):")
            status_result = await session.call_tool(
                "get_status",
                arguments={"username": USERNAME}
            )
            for content in status_result.content:
                if content.type == "text":
                    print(f"   {content.text}\n")

            # 3. Test: upload_pdf
            print(f"📤 Uploading PDF: {pdf_path}")
            pdf_b64 = encode_pdf(pdf_path)
            upload_result = await session.call_tool(
                "upload_pdf",
                arguments={
                    "username": USERNAME,
                    "pdf_base64": pdf_b64,
                    "filename": Path(pdf_path).name
                }
            )
            for content in upload_result.content:
                if content.type == "text":
                    print(f"   {content.text}\n")

            # 4. Test: get_status AFTER upload
            print("📊 get_status (after upload):")
            status_result = await session.call_tool(
                "get_status",
                arguments={"username": USERNAME}
            )
            for content in status_result.content:
                if content.type == "text":
                    print(f"   {content.text}\n")

            # 5. Test: chat
            print(f"💬 chat: {QUESTION}")
            chat_result = await session.call_tool(
                "chat",
                arguments={
                    "username": USERNAME,
                    "question": QUESTION
                }
            )
            for content in chat_result.content:
                if content.type == "text":
                    print(f"   {content.text}\n")

            # 6. (Optional) build_graph if you have a server-side local path
            # print("📦 build_graph (local path – skip if not needed)")
            # build_result = await session.call_tool(
            #     "build_graph",
            #     arguments={"username": USERNAME, "pdf_path": pdf_path}
            # )
            # for content in build_result.content:
            #     if content.type == "text":
            #         print(f"   {content.text}\n")

    print("🏁 All tests completed.")


if __name__ == "__main__":
    asyncio.run(main())