"use client";

import { useCallback, useState } from "react";
import { cn } from "@/lib/utils";

const ACCEPTED_FORMATS = [".pdf", ".dwg", ".dxf", ".jpg", ".jpeg", ".png"];
const ACCEPTED_MIME = "application/pdf,image/jpeg,image/png,.dwg,.dxf";

export function DrawingUploader() {
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<"idle" | "uploading" | "done" | "error">("idle");

  const handleFile = useCallback((f: File) => {
    setFile(f);
    setStatus("idle");
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const f = e.dataTransfer.files[0];
      if (f) handleFile(f);
    },
    [handleFile]
  );

  const handleUpload = async () => {
    if (!file) return;
    setStatus("uploading");
    try {
      // apiClient.uploadDrawing(file) — implemented in Session 2
      await new Promise((r) => setTimeout(r, 500));
      setStatus("done");
    } catch {
      setStatus("error");
    }
  };

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={cn(
          "border-2 border-dashed rounded-xl p-12 text-center transition-colors cursor-pointer",
          dragging ? "border-blue-400 bg-blue-50" : "border-gray-300 hover:border-gray-400"
        )}
        onClick={() => document.getElementById("file-input")?.click()}
      >
        <input
          id="file-input"
          type="file"
          accept={ACCEPTED_MIME}
          className="hidden"
          onChange={(e) => { if (e.target.files?.[0]) handleFile(e.target.files[0]); }}
        />
        <p className="text-3xl mb-3">📄</p>
        <p className="font-medium text-gray-700">Drop a drawing here or click to browse</p>
        <p className="text-sm text-gray-400 mt-1">
          Supported: {ACCEPTED_FORMATS.join(", ")}
        </p>
      </div>

      {/* Selected file */}
      {file && (
        <div className="flex items-center justify-between bg-gray-50 border border-gray-200 rounded-lg px-4 py-3">
          <div>
            <p className="font-medium text-sm">{file.name}</p>
            <p className="text-xs text-gray-400">{(file.size / 1024).toFixed(1)} KB</p>
          </div>
          <button
            onClick={handleUpload}
            disabled={status === "uploading"}
            className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {status === "uploading" ? "Uploading…" : "Upload & Analyze"}
          </button>
        </div>
      )}

      {status === "done" && (
        <p className="text-green-600 text-sm font-medium">
          Drawing uploaded. Design generation will start shortly.
        </p>
      )}
      {status === "error" && (
        <p className="text-red-500 text-sm">Upload failed. Please try again.</p>
      )}

      <p className="text-xs text-gray-400">
        Note: Drawing upload endpoint implemented in Session 2.
      </p>
    </div>
  );
}
