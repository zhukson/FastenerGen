"use client";

import { useCallback, useState } from "react";
import { apiClient, type PartFeatures } from "@/lib/api";
import { cn } from "@/lib/utils";

const ACCEPTED_FORMATS = [".pdf", ".dwg", ".dxf", ".jpg", ".jpeg", ".png"];
const ACCEPTED_MIME = "application/pdf,image/jpeg,image/png,.dwg,.dxf";

type Step = "idle" | "uploading" | "uploaded" | "understanding" | "done" | "generating" | "error";

export function DrawingUploader() {
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [step, setStep] = useState<Step>("idle");
  const [drawingId, setDrawingId] = useState<string | null>(null);
  const [features, setFeatures] = useState<PartFeatures | null>(null);
  const [designId, setDesignId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback((f: File) => {
    setFile(f);
    setStep("idle");
    setFeatures(null);
    setDesignId(null);
    setError(null);
  }, []);

  const handleGenerateDesign = async () => {
    if (!drawingId || !features) return;
    setStep("generating");
    setError(null);
    try {
      const result = await apiClient.generateDesign(drawingId, features);
      setDesignId(result.design_id);
      window.location.href = `/designs/${result.design_id}`;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Design generation failed");
      setStep("error");
    }
  };

  // v2 (2026-05-01 pivot): single-output 过模图 pipeline
  const handleGenerateV2 = async () => {
    if (!drawingId) return;
    setStep("generating");
    setError(null);
    try {
      const result = await apiClient.v2GenerateDesign(drawingId);
      setDesignId(result.design_id);
      window.location.href = `/designs/v2/${result.design_id}`;
    } catch (e) {
      setError(e instanceof Error ? e.message : "v2 generation failed");
      setStep("error");
    }
  };

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
    setStep("uploading");
    setError(null);
    try {
      const result = await apiClient.uploadDrawing(file);
      setDrawingId(result.drawing_id);
      setStep("uploaded");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
      setStep("error");
    }
  };

  const handleUnderstand = async () => {
    if (!drawingId) return;
    setStep("understanding");
    setError(null);
    try {
      const result = await apiClient.understandDrawing(drawingId, file?.name ?? "");
      setFeatures(result);
      setStep("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
      setStep("error");
    }
  };

  return (
    <div className="space-y-5">
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={cn(
          "border-2 border-dashed rounded-xl p-12 text-center transition-colors cursor-pointer",
          dragging ? "border-blue-400 bg-blue-50" : "border-gray-300 hover:border-gray-400"
        )}
        onClick={() => document.getElementById("drawing-input")?.click()}
      >
        <input
          id="drawing-input"
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

      {/* File selected */}
      {file && step === "idle" && (
        <div className="flex items-center justify-between bg-gray-50 border border-gray-200 rounded-lg px-4 py-3">
          <div>
            <p className="font-medium text-sm">{file.name}</p>
            <p className="text-xs text-gray-400">{(file.size / 1024).toFixed(1)} KB</p>
          </div>
          <button
            onClick={handleUpload}
            className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
          >
            Upload
          </button>
        </div>
      )}

      {/* Uploading */}
      {step === "uploading" && (
        <ProgressCard label="Uploading drawing…" />
      )}

      {/* Uploaded — ready to analyze */}
      {step === "uploaded" && drawingId && (
        <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 flex items-center justify-between">
          <div>
            <p className="font-medium text-sm text-green-700">Drawing uploaded ✓</p>
            <p className="text-xs text-gray-400 mt-0.5">ID: {drawingId}</p>
          </div>
          <button
            onClick={handleUnderstand}
            className="px-4 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 transition-colors"
          >
            Analyze Drawing
          </button>
        </div>
      )}

      {/* Analyzing */}
      {step === "understanding" && (
        <ProgressCard label="Analyzing drawing with Claude Vision… (15–30 s)" />
      )}

      {/* Generating design */}
      {step === "generating" && (
        <ProgressCard label="Generating die design… Step 2: Retrieving cases → Step 3: Planning process → Step 4: Designing dies…" />
      )}

      {/* Error */}
      {step === "error" && error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          <p className="text-sm text-red-600 font-medium">Error</p>
          <p className="text-xs text-red-500 mt-0.5">{error}</p>
          <button
            onClick={() => setStep("idle")}
            className="mt-2 text-xs text-red-600 underline"
          >
            Try again
          </button>
        </div>
      )}

      {/* Results */}
      {step === "done" && features && (
        <FeaturesPanel
          features={features}
          onGenerateDesign={handleGenerateDesign}
          onGenerateV2={handleGenerateV2}
        />
      )}

      {/* v2 quick path — skip features review, go straight to 过模图 */}
      {step === "uploaded" && drawingId && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
          <p className="text-xs text-amber-700 font-medium mb-1.5">
            Or skip review and run the v2 单输出过模图 pipeline directly
          </p>
          <button
            onClick={handleGenerateV2}
            className="px-4 py-1.5 bg-amber-600 text-white text-sm rounded-lg hover:bg-amber-700 transition-colors"
          >
            Generate 过模图 (v2)
          </button>
        </div>
      )}
    </div>
  );
}

function ProgressCard({ label }: { label: string }) {
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3">
      <div className="flex items-center gap-3">
        <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-blue-700">{label}</p>
      </div>
    </div>
  );
}

function FeaturesPanel({
  features,
  onGenerateDesign,
  onGenerateV2,
}: {
  features: PartFeatures;
  onGenerateDesign?: () => void;
  onGenerateV2?: () => void;
}) {
  // v2: head/shank/thread are now optional (异形件 may have none of them).
  const head = features.head;
  const shank = features.shank;
  const thread = features.thread;
  const rows: Array<[string, string | number | null]> = [
    ["Part No.", features.part_number],
    ["Description", features.description],
    ["Overall Length", features.overall_length ? `${features.overall_length} mm` : null],
    ["Head Type", head?.type ?? null],
    ["Head ⌀", head?.diameter ? `⌀${head.diameter} mm` : null],
    ["Head Height", head?.height ? `${head.height} mm` : null],
    ["Shank ⌀", shank?.diameter ? `⌀${shank.diameter} mm` : null],
    ["Thread", thread?.spec ?? null],
    ["Thread Length", thread?.length ? `${thread.length} mm` : null],
    ["Material", features.material_grade],
    ["Grade", features.strength_grade],
    ["HRC (core)", features.core_hardness_min_hrc != null && features.core_hardness_max_hrc != null
      ? `${features.core_hardness_min_hrc}–${features.core_hardness_max_hrc}` : null],
    ["Surface", features.surface_treatment],
    ["Standard", features.standard],
  ];

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4 gap-2">
        <h3 className="font-semibold">Extracted Features</h3>
        <div className="flex gap-2">
          {onGenerateV2 && (
            <button
              onClick={onGenerateV2}
              className="px-3 py-1.5 bg-amber-600 text-white text-sm rounded-lg hover:bg-amber-700 transition-colors"
              title="v2: single 过模图 DXF (preferred)"
            >
              Generate 过模图 (v2)
            </button>
          )}
          {onGenerateDesign && (
            <button
              onClick={onGenerateDesign}
              className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
              title="v1: legacy multi-file output"
            >
              Generate Die Design (v1)
            </button>
          )}
        </div>
      </div>

      <div className="space-y-1.5">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between text-sm">
            <span className="text-gray-500 shrink-0 w-32">{label}</span>
            <span
              className={cn(
                "font-mono text-right",
                value == null ? "text-yellow-500 italic" : "text-gray-800"
              )}
            >
              {value ?? "not found"}
            </span>
          </div>
        ))}
      </div>

      {features.notes.length > 0 && (
        <div className="mt-4 pt-3 border-t border-gray-100">
          <p className="text-xs text-gray-400 mb-1">Notes</p>
          {features.notes.map((note, i) => (
            <p key={i} className="text-xs text-gray-600">{note}</p>
          ))}
        </div>
      )}
    </div>
  );
}
