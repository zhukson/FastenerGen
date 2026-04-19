"use client";

/**
 * Download panel for generated output files (DWG, STEP, STL).
 * Implemented in Session 4 when file generation pipeline is available.
 */
export function FileDownloadPanel({ designId }: { designId: string }) {
  const files = [
    { label: "Production Drawing", format: "DXF", icon: "📐" },
    { label: "Die Drawing (all stations)", format: "DXF", icon: "📐" },
    { label: "3D Models", format: "STEP", icon: "📦" },
    { label: "3D Preview", format: "STL", icon: "🖥" },
  ];

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <h2 className="font-semibold text-sm mb-3">Download Files</h2>
      <div className="space-y-2">
        {files.map((f) => (
          <button
            key={f.label}
            disabled
            className="w-full flex items-center justify-between text-sm px-3 py-2 rounded-lg border border-gray-200 opacity-50 cursor-not-allowed"
          >
            <span className="flex items-center gap-2">
              <span>{f.icon}</span>
              <span>{f.label}</span>
            </span>
            <span className="text-xs font-mono text-gray-400">{f.format}</span>
          </button>
        ))}
      </div>
      <p className="text-xs text-gray-400 mt-3">Downloads available in Session 4</p>
    </div>
  );
}
