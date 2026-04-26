"use client";

import { apiClient, type OutputFile } from "@/lib/api";

interface FileDownloadPanelProps {
  designId: string;
  files?: OutputFile[];
}

const FORMAT_ICONS: Record<string, string> = {
  dxf: "📐",
  step: "📦",
  stl: "🖥",
  json: "📄",
};

const FILE_TYPE_LABELS: Record<string, string> = {
  production_drawing: "Production Drawing",
  process_breakdown: "Process Breakdown",
  punch_drawing: "Punch Drawing",
  die_drawing: "Die Drawing",
  punch_stl: "Punch 3D",
  die_stl: "Die 3D",
  punch_step: "Punch STEP",
  die_step: "Die STEP",
  workpiece_stl: "Workpiece 3D",
  assembly_preview: "Assembly Preview",
  blank_stl: "Blank 3D",
  parameters: "Parameters JSON",
};

function getRelativePath(file: OutputFile, designId: string): string {
  const fp = file.file_path;
  const marker = designId + "/";
  const idx = fp.indexOf(marker);
  return idx >= 0 ? fp.slice(idx + marker.length) : fp.split("/").pop()!;
}

export function FileDownloadPanel({ designId, files = [] }: FileDownloadPanelProps) {
  const primary = files.filter((f) =>
    ["production_drawing", "process_breakdown"].includes(f.file_type),
  );
  const stationDxf = files
    .filter((f) => f.station_number !== null && f.format === "dxf")
    .sort((a, b) => (a.station_number ?? 0) - (b.station_number ?? 0));

  const displayFiles = [...primary, ...stationDxf];

  const handleDownload = (file: OutputFile) => {
    const rel = getRelativePath(file, designId);
    window.open(apiClient.downloadFile(designId, rel), "_blank");
  };

  const stlCount = files.filter((f) => f.format === "stl").length;
  const stepCount = files.filter((f) => f.format === "step").length;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <h2 className="font-semibold text-sm mb-3">All Files</h2>

      {files.length === 0 ? (
        <p className="text-xs text-gray-400">No output files generated yet.</p>
      ) : (
        <>
          <div className="space-y-1.5">
            {displayFiles.map((f) => {
              const icon = FORMAT_ICONS[f.format] ?? "📄";
              const label =
                FILE_TYPE_LABELS[f.file_type] ??
                (f.station_number != null
                  ? `S${f.station_number} ${f.file_type.replace(/_/g, " ")}`
                  : f.file_type);
              const sizeKb = f.size_bytes ? Math.round(f.size_bytes / 1024) : null;
              const key = `${f.file_type}-${f.station_number}`;

              return (
                <button
                  key={key}
                  onClick={() => handleDownload(f)}
                  className="w-full flex items-center text-sm px-3 py-2 rounded-lg border border-gray-200 hover:bg-gray-50 hover:border-gray-300 transition-colors text-left"
                >
                  <div className="flex-1 flex items-center gap-2 min-w-0">
                    <span className="shrink-0">{icon}</span>
                    <span className="truncate">{label}</span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0 ml-2">
                    {sizeKb && <span className="text-xs text-gray-400">{sizeKb}KB</span>}
                    <span className="text-xs font-mono text-gray-400 uppercase">{f.format}</span>
                  </div>
                </button>
              );
            })}
          </div>

          {(stlCount > 0 || stepCount > 0) && (
            <div className="mt-3 pt-3 border-t border-gray-100 flex gap-4 text-xs text-gray-500">
              {stlCount > 0 && (
                <span>
                  <span className="font-medium text-gray-700">{stlCount}</span> STL files (in 3D viewer)
                </span>
              )}
              {stepCount > 0 && (
                <span>
                  <span className="font-medium text-gray-700">{stepCount}</span> STEP files
                </span>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
