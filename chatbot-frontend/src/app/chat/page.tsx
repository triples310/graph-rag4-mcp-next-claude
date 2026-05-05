"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import ChatWindow from "@/components/ChatWindow";
import { apiLogout, apiStatus, Message } from "@/lib/api";

interface ChatSession {
  id: string;
  label: string;
  messages: Message[];
}

function makeSession(): ChatSession {
  return {
    id: Date.now().toString(),
    label: `Chat ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`,
    messages: [],
  };
}

export default function ChatPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [pdfName, setPdfName] = useState<string | null>(null);
  const [hasGraph, setHasGraph] = useState(false);
  const [mcpConnected, setMcpConnected] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([makeSession()]);
  const [activeChatId, setActiveChatId] = useState<string>("");

  // Auth guard + load user state
  useEffect(() => {
    const token = localStorage.getItem("token");
    const user = localStorage.getItem("username");
    if (!token || !user) {
      router.replace("/login");
      return;
    }
    setUsername(user);
    setSessions((s) => {
      const first = s[0];
      setActiveChatId(first.id);
      return s;
    });

    // Check graph status
    apiStatus()
      .then((data) => {
        setHasGraph(data.has_graph);
        setPdfName(data.pdf_name || null);
      })
      .catch(() => {});
  }, [router]);

  const activeSession = sessions.find((s) => s.id === activeChatId) ?? sessions[0];

  function handleNewMessage(msg: Message) {
    setSessions((prev) =>
      prev.map((s) =>
        s.id === activeChatId
          ? { ...s, messages: [...s.messages, msg] }
          : s
      )
    );
  }

  function handleNewChat() {
    const session = makeSession();
    setSessions((prev) => [...prev, session]);
    setActiveChatId(session.id);
  }

  function handleSelectChat(id: string) {
    setActiveChatId(id);
  }

  function handlePdfUploaded(name: string) {
    setPdfName(name);
    setHasGraph(true);
  }

  async function handleLogout() {
    await apiLogout();
    router.replace("/login");
  }

  if (!username) return null;

  return (
    <div style={styles.layout}>
      <Sidebar
        username={username}
        pdfName={pdfName}
        hasGraph={hasGraph}
        onPdfUploaded={handlePdfUploaded}
        onLogout={handleLogout}
        mcpConnected={mcpConnected}
        onMcpToggle={() => setMcpConnected((v) => !v)}
        chatSessions={sessions.map((s) => ({ id: s.id, label: s.label }))}
        activeChatId={activeChatId}
        onSelectChat={handleSelectChat}
        onNewChat={handleNewChat}
      />
      <main style={styles.main}>
        <ChatWindow
          messages={activeSession?.messages ?? []}
          onNewMessage={handleNewMessage}
          hasGraph={hasGraph}
          pdfName={pdfName}
        />
      </main>

      {/* Typing dot animation */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.2; transform: scale(0.8); }
          50% { opacity: 1; transform: scale(1); }
        }
        input:focus, textarea:focus {
          border-color: #333 !important;
        }
        button:hover:not(:disabled) {
          opacity: 0.85;
        }
      `}</style>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  layout: {
    display: "flex",
    height: "100vh",
    overflow: "hidden",
    background: "#0a0a0a",
  },
  main: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
};