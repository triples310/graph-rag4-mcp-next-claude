"use client";
import { useState } from "react";
import UploadModal from "./UploadModal";

interface Props {
  username: string;
  pdfName: string | null;
  hasGraph: boolean;
  onPdfUploaded: (name: string) => void;
  onLogout: () => void;
  mcpConnected: boolean;
  onMcpToggle: () => void;
  chatSessions: { id: string; label: string }[];
  activeChatId: string;
  onSelectChat: (id: string) => void;
  onNewChat: () => void;
}

export default function Sidebar({
  username, pdfName, hasGraph, onPdfUploaded, onLogout,
  mcpConnected, onMcpToggle, chatSessions, activeChatId, onSelectChat, onNewChat,
}: Props) {
  const [showUpload, setShowUpload] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [showMcp, setShowMcp] = useState(false);

  return (
    <>
      <aside className="w-60 shrink-0 h-screen bg-white border-r border-gray-100 flex flex-col">

        {/* Brand */}
        <div className="flex items-center gap-2.5 px-4 py-4 border-b border-gray-100">
          <div className="w-7 h-7 bg-black rounded-md flex items-center justify-center shrink-0">
            <span className="text-white text-xs font-bold">G</span>
          </div>
          <span className="text-sm font-semibold text-black tracking-tight">GraphRAG</span>
        </div>

        {/* New chat row */}
        <div className="flex items-center gap-2 px-3 py-3 border-b border-gray-100">
          <button onClick={onNewChat}
            className="flex-1 flex items-center gap-2 text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-2 hover:bg-gray-50 hover:text-black transition-colors">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            New chat
          </button>

          {/* ··· menu button */}
          <div className="relative">
            <button
              onClick={() => setShowMenu(v => !v)}
              className="w-8 h-8 flex items-center justify-center border border-gray-200 rounded-lg text-gray-400 hover:text-black hover:bg-gray-50 transition-colors"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="5" cy="12" r="1.5" fill="currentColor" />
                <circle cx="12" cy="12" r="1.5" fill="currentColor" />
                <circle cx="19" cy="12" r="1.5" fill="currentColor" />
              </svg>
            </button>

            {showMenu && (
              <div className="absolute top-9 right-0 w-48 bg-white border border-gray-200 rounded-xl shadow-lg z-50 overflow-hidden">
                <button
                  onClick={() => { setShowMenu(false); setShowUpload(true); }}
                  className="flex items-center gap-2.5 w-full px-3.5 py-2.5 text-xs text-gray-700 hover:bg-gray-50 transition-colors border-b border-gray-100"
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="12" y1="18" x2="12" y2="12" /><line x1="9" y1="15" x2="15" y2="15" />
                  </svg>
                  Upload PDF
                </button>
                <button
                  onClick={() => { setShowMenu(false); setShowMcp(true); }}
                  className="flex items-center gap-2.5 w-full px-3.5 py-2.5 text-xs text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                    <rect x="2" y="3" width="20" height="14" rx="2" />
                    <line x1="8" y1="21" x2="16" y2="21" /><line x1="12" y1="17" x2="12" y2="21" />
                  </svg>
                  Connect MCP Server
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Chat sessions */}
        <div className="flex-1 overflow-y-auto py-2 px-2">
          {chatSessions.length === 0 ? (
            <p className="text-xs text-gray-300 text-center mt-6">No chats yet</p>
          ) : (
            chatSessions.map((s) => (
              <button key={s.id} onClick={() => onSelectChat(s.id)}
                className={`flex items-center gap-2 w-full text-left px-3 py-2 rounded-lg text-xs mb-0.5 transition-colors truncate
                  ${s.id === activeChatId ? "bg-gray-100 text-black font-medium" : "text-gray-500 hover:bg-gray-50 hover:text-black"}`}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="shrink-0">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                <span className="truncate">{s.label}</span>
              </button>
            ))
          )}
        </div>

        {/* Bottom status + user */}
        <div className="border-t border-gray-100 px-3 py-3 flex flex-col gap-2">
          {/* PDF status */}
          <div className="flex items-center gap-2">
            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${hasGraph ? "bg-green-500" : "bg-gray-300"}`} />
            <span className="text-xs text-gray-400 truncate">{pdfName ?? "No PDF uploaded"}</span>
          </div>
          {/* MCP status */}
          <div className="flex items-center gap-2">
            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${mcpConnected ? "bg-green-500" : "bg-gray-300"}`} />
            <span className="text-xs text-gray-400">MCP: {mcpConnected ? "Connected" : "Disconnected"}</span>
          </div>

          <div className="h-px bg-gray-100 my-0.5" />

          {/* User row */}
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-gray-100 border border-gray-200 rounded-full flex items-center justify-center text-xs font-semibold text-gray-500 shrink-0">
              {username[0]?.toUpperCase()}
            </div>
            <span className="text-xs text-gray-500 flex-1 truncate">{username}</span>
            <button onClick={onLogout} title="Sign out"
              className="text-gray-300 hover:text-black transition-colors p-0.5">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
            </button>
          </div>
        </div>
      </aside>

      {showUpload && (
        <UploadModal onClose={() => setShowUpload(false)} onSuccess={(n) => { setShowUpload(false); onPdfUploaded(n); }} />
      )}

      {showMcp && (
        <McpModal connected={mcpConnected} onToggle={() => { onMcpToggle(); setShowMcp(false); }} onClose={() => setShowMcp(false)} />
      )}

      {showMenu && (
        <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
      )}
    </>
  );
}

function McpModal({ connected, onToggle, onClose }: { connected: boolean; onToggle: () => void; onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 px-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="bg-white rounded-2xl w-full max-w-sm p-6 shadow-xl">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-black">MCP Server</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-black text-lg leading-none">✕</button>
        </div>

        <div className="mb-4">
          <p className="text-xs text-gray-400 mb-2 uppercase tracking-wider">Endpoint</p>
          <div className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
            <code className="text-xs text-gray-600">http://localhost:8001/mcp</code>
          </div>
        </div>

        <div className="mb-5">
          <p className="text-xs text-gray-400 mb-2 uppercase tracking-wider">Available tools</p>
          {["upload_pdf", "chat", "get_status", "build_graph"].map((t) => (
            <div key={t} className="flex items-center gap-2 py-1">
              <span className="w-1 h-1 rounded-full bg-gray-300" />
              <code className="text-xs text-gray-500">{t}</code>
            </div>
          ))}
        </div>

        <button onClick={onToggle}
          className={`w-full py-2.5 rounded-xl text-sm font-semibold transition-colors
            ${connected ? "bg-white text-red-500 border border-red-200 hover:bg-red-50" : "bg-black text-white hover:bg-neutral-800"}`}>
          {connected ? "Disconnect" : "Connect to MCP Server"}
        </button>
      </div>
    </div>
  );
}