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
  punch_drawing: "Die Drawing (all stations)",
  die_drawing: "Die Drawing",
  punch_stl: "Punch STL",
  die_stl: "Die STL",
  punch_step: "Punch STEP",
  die_step: "Die STEP",
  parameters: "Parameters JSON",
};

export function FileDownloadPanel({ designId, files = [] }: FileDownloadPanelProps) {
  // Group files by type priority: drawings first, then 3D per station
  const primary = files.filter((f) =>
    ["production_drawing", "process_breakdown"].includes(f.file_type)
  );
  const stationFiles = files
    .filter((f) => f.station_number !== null && f.format !== "step")
    .sort((a, b) => (a.station_number ?? 0) - (b.station_number ?? 0));

  const allFiles = [...primary, ...stationFiles];

  const handleDownload = (file: OutputFile) => {
    const fileName = file.file_path.split("/").pop() ?? file.file_type;
    const url = apiClient.downloadFile(designId, fileName);
    window.open(url, "_blank");
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <h2 className="font-semibold text-sm mb-3">Download Files</h2>

      {allFiles.length === 0 ? (
        <p className="text-xs text-gray-400">No output files generated yet.</p>
      ) : (
        <div className="space-y-1.5">
          {allFiles.map((f) => {
            const icon = FORMAT_ICONS[f.format] ?? "📄";
            const label =
              FILE_TYPE_LABELS[f.file_type] ??
              (f.station_number != null
                ? `S${f.station_number} ${f.file_type.replace("_", " ")}`
                : f.file_type);
            const sizeKb = f.size_bytes ? Math.round(f.size_bytes / 1024) : null;

            return (
              <button
                key={`${f.file_type}-${f.station_number}`}
                onClick={() => handleDownload(f)}
                className="w-full flex items-center justify-between text-sm px-3 py-2 rounded-lg border border-gray-200 hover:bg-gray-50 hover:border-gray-300 transition-colors"
              >
                <span className="flex items-center gap-2 min-w-0">
                  <span className="shrink-0">{icon}</span>
                  <span className="truncate text-left">{label}</span>
                </span>
                <span className="flex items-center gap-1 shrink-0 ml-2">
                  {sizeKb && <span className="text-xs text-gray-400">{sizeKb}KB</span>}
                  <span className="text-xs font-mono text-gray-400 uppercase">{f.format}</span>
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
