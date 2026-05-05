"use client";
import { useState, useRef, useEffect } from "react";
import { apiChat, Message } from "@/lib/api";

interface Props {
  messages: Message[];
  onNewMessage: (msg: Message) => void;
  hasGraph: boolean;
  pdfName: string | null;
}

export default function ChatWindow({ messages, onNewMessage, hasGraph, pdfName }: Props) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
  }, [input]);

  async function handleSend() {
    const q = input.trim();
    if (!q || loading) return;
    onNewMessage({ id: Date.now().toString(), role: "user", content: q, timestamp: new Date() });
    setInput("");
    setLoading(true);
    try {
      const data = await apiChat(q);
      onNewMessage({ id: (Date.now() + 1).toString(), role: "assistant", content: data.answer, timestamp: new Date() });
    } catch (err: unknown) {
      onNewMessage({ id: (Date.now() + 1).toString(), role: "assistant", content: err instanceof Error ? err.message : "Something went wrong.", timestamp: new Date() });
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  }

  return (
    <div className="flex flex-col h-screen bg-white">

      {/* Messages */}
      <div className="flex-1 overflow-y-auto py-8">
        {messages.length === 0 ? (
          <EmptyState hasGraph={hasGraph} pdfName={pdfName} />
        ) : (
          <div className="max-w-2xl mx-auto px-4 flex flex-col gap-5">
            {messages.map((msg) => <MessageBubble key={msg.id} msg={msg} />)}
            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>
        )}
        {messages.length === 0 && <div ref={bottomRef} />}
      </div>

      {/* Input bar */}
      <div className="border-t border-gray-100 px-4 py-4 bg-white">
        <div className="max-w-2xl mx-auto">
          <div className="flex items-end gap-2 bg-white border border-gray-200 rounded-2xl px-4 py-3 focus-within:border-black transition-colors">
            <textarea
              ref={textareaRef}
              suppressHydrationWarning
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={hasGraph ? "Ask about your document..." : "Upload a PDF to get started"}
              rows={1}
              disabled={loading}
              className="flex-1 resize-none bg-transparent text-sm text-black placeholder-gray-400 focus:outline-none leading-relaxed min-h-[24px] max-h-[160px] overflow-y-auto"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || loading}
              className="w-8 h-8 bg-black rounded-xl flex items-center justify-center shrink-0 hover:bg-neutral-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.2">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" fill="white" stroke="none" />
              </svg>
            </button>
          </div>
          <p className="text-xs text-gray-300 text-center mt-2">Enter to send · Shift+Enter for new line</p>
        </div>
      </div>

      <style>{`@keyframes bounce-dot { 0%,80%,100%{transform:scale(0.6);opacity:0.4} 40%{transform:scale(1);opacity:1} }`}</style>
    </div>
  );
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex items-end gap-2.5 ${isUser ? "flex-row-reverse" : ""}`}>
      {!isUser && (
        <div className="w-7 h-7 bg-black rounded-full flex items-center justify-center shrink-0 mb-1">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
            <circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12" />
          </svg>
        </div>
      )}
      <div className={`max-w-[75%] rounded-2xl px-4 py-3 ${isUser ? "bg-black text-white rounded-br-sm" : "bg-gray-100 text-black rounded-bl-sm"}`}>
        <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{msg.content}</p>
        <span className={`text-[10px] mt-1.5 block ${isUser ? "text-white/50" : "text-gray-400"}`}>
          {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </span>
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-end gap-2.5">
      <div className="w-7 h-7 bg-black rounded-full flex items-center justify-center shrink-0">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
          <circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12" />
        </svg>
      </div>
      <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-3">
        <div className="flex gap-1 items-center h-4">
          {[0, 150, 300].map((delay) => (
            <span key={delay} className="w-1.5 h-1.5 bg-gray-400 rounded-full inline-block"
              style={{ animation: `bounce-dot 1.2s ease-in-out ${delay}ms infinite` }} />
          ))}
        </div>
      </div>
    </div>
  );
}

function EmptyState({ hasGraph, pdfName }: { hasGraph: boolean; pdfName: string | null }) {
  const suggestions = ["Who are the executives?", "What are the primary services?", "Tell me the mission statement", "Show the financial overview"];
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-4 text-center">
      <div className="w-12 h-12 bg-gray-100 rounded-2xl flex items-center justify-center mb-5">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#999" strokeWidth="1.5">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      </div>
      <h2 className="text-lg font-semibold text-black mb-2 tracking-tight">
        {hasGraph ? `Chatting with ${pdfName}` : "No document loaded"}
      </h2>
      <p className="text-sm text-gray-400 max-w-xs leading-relaxed mb-6">
        {hasGraph
          ? "Ask me anything about your document. I'll query the knowledge graph."
          : "Use the sidebar menu to upload a PDF and build your knowledge graph."}
      </p>
      {hasGraph && (
        <div className="flex flex-wrap gap-2 justify-center max-w-sm">
          {suggestions.map((s) => (
            <span key={s} className="text-xs text-gray-500 bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5">{s}</span>
          ))}
        </div>
      )}
    </div>
  );
}