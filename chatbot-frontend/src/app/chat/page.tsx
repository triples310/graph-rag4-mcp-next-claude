"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import ChatWindow from "@/components/Chatwindow";
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
  const [username] = useState<string>(() => (typeof window === "undefined" ? "" : localStorage.getItem("username") ?? ""));
  const [pdfName, setPdfName] = useState<string | null>(null);
  const [hasGraph, setHasGraph] = useState(false);
  const [mcpConnected, setMcpConnected] = useState(false);
  const initialSession = makeSession();
  const [sessions, setSessions] = useState<ChatSession[]>([initialSession]);
  const [activeChatId, setActiveChatId] = useState<string>(initialSession.id);

  // Auth guard + load user state
  useEffect(() => {
    const token = localStorage.getItem("token");
    const user = localStorage.getItem("username");
    if (!token || !user) {
      router.replace("/login");
      return;
    }
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
    <div className="flex h-screen overflow-hidden bg-black">
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
      <main className="flex flex-1 flex-col overflow-hidden">
        <ChatWindow
          messages={activeSession?.messages ?? []}
          onNewMessage={handleNewMessage}
          hasGraph={hasGraph}
          pdfName={pdfName}
        />
      </main>
    </div>
  );
}
