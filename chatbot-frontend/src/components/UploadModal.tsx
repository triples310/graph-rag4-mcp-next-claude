"use client";
import { useState, useRef, useCallback } from "react";
import { apiUploadPDF } from "@/lib/api";

interface Props {
  onClose: () => void;
  onSuccess: (pdfName: string) => void;
}

export default function UploadModal({ onClose, onSuccess }: Props) {
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f?.type === "application/pdf") { setFile(f); setError(""); }
    else setError("Only PDF files are accepted.");
  }, []);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError("");
    setProgress("Building knowledge graph...");
    try {
      const result = await apiUploadPDF(file);
      setProgress(`Done! ${result.nodes_created} nodes created.`);
      setTimeout(() => onSuccess(file.name), 800);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setProgress("");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 px-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-white rounded-2xl w-full max-w-md p-6 shadow-xl">

        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-black">Upload PDF</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-black transition-colors text-lg leading-none">✕</button>
        </div>

        {/* Drop zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center gap-3 cursor-pointer transition-colors
            ${dragging ? "border-black bg-gray-50" : "border-gray-200 hover:border-gray-400"}`}
        >
          <input ref={inputRef} type="file" accept=".pdf" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) { setFile(f); setError(""); } }} />
          <div className="w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center text-gray-400">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="12" y1="18" x2="12" y2="12" /><line x1="9" y1="15" x2="15" y2="15" />
            </svg>
          </div>
          {file ? (
            <div className="text-center">
              <p className="text-sm font-medium text-black">{file.name}</p>
              <p className="text-xs text-gray-400 mt-1">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
            </div>
          ) : (
            <div className="text-center">
              <p className="text-sm text-gray-600">Drop your PDF here</p>
              <p className="text-xs text-gray-400 mt-1">or click to browse — max 20MB</p>
            </div>
          )}
        </div>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mt-3">{error}</p>
        )}
        {progress && (
          <p className="text-sm text-gray-500 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 mt-3">{progress}</p>
        )}

        {/* Actions */}
        <div className="flex gap-2 mt-5 justify-end">
          <button onClick={onClose} disabled={uploading}
            className="px-4 py-2 text-sm text-gray-500 border border-gray-200 rounded-xl hover:bg-gray-50 disabled:opacity-50 transition-colors">
            Cancel
          </button>
          <button onClick={handleUpload} disabled={!file || uploading}
            className="px-4 py-2 text-sm font-semibold bg-black text-white rounded-xl hover:bg-neutral-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
            {uploading ? "Processing..." : "Upload & Build Graph"}
          </button>
        </div>
      </div>
    </div>
  );
}