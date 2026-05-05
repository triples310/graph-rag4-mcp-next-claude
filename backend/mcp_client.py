"""
mcp_client.py — Test client for GraphRAG MCP Server (streamable-http)
Usage:
    python mcp_client.py                          # interactive menu
    python mcp_client.py status alice             # quick status check
    python mcp_client.py chat alice "who is CEO"  # quick chat
    python mcp_client.py upload alice ./file.pdf  # quick upload
"""

import sys
import json
import base64
import argparse
from pathlib import Path

import httpx

# ========================= CONFIG =========================

SERVER_URL = "http://localhost:8001/mcp"

HEADERS_BASE = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

# ========================= LOW-LEVEL CLIENT =========================

class MCPClient:
    """
    Minimal MCP streamable-http client.
    Handles: initialize → session → tool calls.
    """

    def __init__(self, server_url: str = SERVER_URL, timeout: int = 120):
        self.server_url  = server_url
        self.timeout     = timeout
        self.session_id  = None
        self._req_id     = 0

    # ---------- helpers ----------

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _headers(self) -> dict:
        h = dict(HEADERS_BASE)
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    def _parse_sse(self, raw: str) -> dict | None:
        """Extract the JSON payload from an SSE 'data:' line."""
        for line in raw.splitlines():
            if line.startswith("data:"):
                return json.loads(line[len("data:"):].strip())
        return None

    # ---------- protocol ----------

    def initialize(self) -> bool:
        """Send MCP initialize handshake and store session ID."""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "py-test-client", "version": "1.0.0"},
            },
        }
        try:
            r = httpx.post(
                self.server_url,
                headers=self._headers(),
                json=payload,
                timeout=self.timeout,
            )
            r.raise_for_status()

            # Grab session ID from response header
            self.session_id = r.headers.get("mcp-session-id")
            if not self.session_id:
                print("❌  No mcp-session-id in response headers.")
                return False

            data = self._parse_sse(r.text)
            if data and "result" in data:
                info = data["result"].get("serverInfo", {})
                print(f"✅  Connected — server: {info.get('name')} v{info.get('version')}")
                print(f"    Session ID: {self.session_id}\n")
                return True

            print(f"❌  Unexpected initialize response: {r.text}")
            return False

        except Exception as e:
            print(f"❌  Initialize failed: {e}")
            return False

    def notify_initialized(self):
        """Send the required notifications/initialized message."""
        payload = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        try:
            httpx.post(
                self.server_url,
                headers=self._headers(),
                json=payload,
                timeout=10,
            )
        except Exception:
            pass   # notification — fire and forget

    def connect(self) -> bool:
        """Full handshake: initialize + notify."""
        ok = self.initialize()
        if ok:
            self.notify_initialized()
        return ok

    # ---------- tool call ----------

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call an MCP tool and return the result dict."""
        if not self.session_id:
            raise RuntimeError("Not connected. Call connect() first.")

        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        r = httpx.post(
            self.server_url,
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()

        data = self._parse_sse(r.text)
        if data is None:
            raise ValueError(f"Could not parse SSE response:\n{r.text}")

        if "error" in data:
            err = data["error"]
            raise RuntimeError(f"MCP error {err['code']}: {err['message']}")

        # Unwrap MCP content envelope
        result = data.get("result", {})

        # Prefer structuredContent if present
        if "structuredContent" in result:
            return result["structuredContent"]

        # Fall back to parsing text content
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            try:
                return json.loads(content[0]["text"])
            except json.JSONDecodeError:
                return {"text": content[0]["text"]}

        return result

    def list_tools(self) -> list:
        """Fetch the list of available tools from the server."""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
        }
        r = httpx.post(
            self.server_url,
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        data = self._parse_sse(r.text)
        return data.get("result", {}).get("tools", [])


# ========================= HIGH-LEVEL HELPERS =========================

def fmt(result: dict) -> str:
    return json.dumps(result, indent=2)


def do_status(client: MCPClient, username: str):
    print(f"📡  get_status(username='{username}')")
    result = client.call_tool("get_status", {"username": username})
    print(fmt(result))


def do_chat(client: MCPClient, username: str, question: str):
    print(f"💬  chat(username='{username}', question='{question}')")
    print("    (this may take a while — LLM is thinking...)\n")
    result = client.call_tool("chat", {"username": username, "question": question})
    print(f"Q: {result.get('question')}")
    print(f"A: {result.get('answer')}")


def do_upload(client: MCPClient, username: str, pdf_path: str):
    path = Path(pdf_path)
    if not path.exists():
        print(f"❌  File not found: {pdf_path}")
        return
    print(f"📤  upload_pdf(username='{username}', file='{path.name}')")
    pdf_b64 = base64.b64encode(path.read_bytes()).decode()
    result = client.call_tool("upload_pdf", {
        "username":   username,
        "pdf_base64": pdf_b64,
        "filename":   path.name,
    })
    print(fmt(result))


def do_build(client: MCPClient, username: str, pdf_path: str):
    print(f"🔨  build_graph(username='{username}', pdf_path='{pdf_path}')")
    result = client.call_tool("build_graph", {
        "username": username,
        "pdf_path": pdf_path,
    })
    print(fmt(result))


def do_list_tools(client: MCPClient):
    print("🔧  Available tools on server:\n")
    tools = client.list_tools()
    for t in tools:
        print(f"  • {t['name']}")
        desc = t.get("description", "")
        if desc:
            print(f"    {desc}")
    print()


# ========================= INTERACTIVE MENU =========================

def interactive_menu(client: MCPClient):
    print("=" * 55)
    print("  GraphRAG MCP Test Client — Interactive Mode")
    print("=" * 55)
    print("Commands:")
    print("  1  get_status   <username>")
    print("  2  chat         <username>  <question>")
    print("  3  upload_pdf   <username>  <pdf_path>")
    print("  4  build_graph  <username>  <pdf_path>")
    print("  5  list tools")
    print("  q  quit")
    print()

    while True:
        try:
            raw = input("mcp> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not raw:
            continue

        parts = raw.split(maxsplit=2)
        cmd   = parts[0].lower()

        try:
            if cmd in ("q", "quit", "exit"):
                print("Bye!")
                break

            elif cmd in ("1", "status"):
                username = parts[1] if len(parts) > 1 else input("  username: ").strip()
                do_status(client, username)

            elif cmd in ("2", "chat"):
                username = parts[1] if len(parts) > 1 else input("  username: ").strip()
                question = parts[2] if len(parts) > 2 else input("  question: ").strip()
                do_chat(client, username, question)

            elif cmd in ("3", "upload"):
                username = parts[1] if len(parts) > 1 else input("  username: ").strip()
                pdf_path = parts[2] if len(parts) > 2 else input("  pdf path: ").strip()
                do_upload(client, username, pdf_path)

            elif cmd in ("4", "build"):
                username = parts[1] if len(parts) > 1 else input("  username: ").strip()
                pdf_path = parts[2] if len(parts) > 2 else input("  pdf path: ").strip()
                do_build(client, username, pdf_path)

            elif cmd in ("5", "tools", "list"):
                do_list_tools(client)

            else:
                print(f"  Unknown command: '{cmd}'. Type 'q' to quit.")

        except RuntimeError as e:
            print(f"  ❌  Server error: {e}")
        except Exception as e:
            print(f"  ❌  Error: {e}")

        print()


# ========================= ENTRY POINT =========================

def main():
    parser = argparse.ArgumentParser(
        description="MCP test client for GraphRAG server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python mcp_client.py                              # interactive menu
  python mcp_client.py status alice
  python mcp_client.py chat alice "who is the CEO"
  python mcp_client.py upload alice ./company.pdf
  python mcp_client.py build  alice C:/data/doc.pdf
  python mcp_client.py tools
        """,
    )
    parser.add_argument("command",  nargs="?", help="status | chat | upload | build | tools")
    parser.add_argument("username", nargs="?", help="username")
    parser.add_argument("extra",    nargs="?", help="question or pdf_path")
    parser.add_argument("--url",    default=SERVER_URL, help=f"Server URL (default: {SERVER_URL})")
    args = parser.parse_args()

    client = MCPClient(server_url=args.url)

    print(f"🔌  Connecting to {args.url} ...")
    if not client.connect():
        sys.exit(1)

    if args.command is None:
        interactive_menu(client)

    elif args.command == "status":
        if not args.username:
            parser.error("status requires <username>")
        do_status(client, args.username)

    elif args.command == "chat":
        if not args.username or not args.extra:
            parser.error("chat requires <username> <question>")
        do_chat(client, args.username, args.extra)

    elif args.command == "upload":
        if not args.username or not args.extra:
            parser.error("upload requires <username> <pdf_path>")
        do_upload(client, args.username, args.extra)

    elif args.command == "build":
        if not args.username or not args.extra:
            parser.error("build requires <username> <pdf_path>")
        do_build(client, args.username, args.extra)

    elif args.command == "tools":
        do_list_tools(client)

    else:
        print(f"Unknown command: '{args.command}'")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()