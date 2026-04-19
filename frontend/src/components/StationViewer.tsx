"use client";

/**
 * Per-station 3D viewer with tab/carousel selector.
 * Loads punch + die + workpiece STL for the selected station.
 * Implemented in Session 4.
 */
export function StationViewer({
  designId,
  stationCount = 3,
}: {
  designId: string;
  stationCount?: number;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <div className="flex gap-2 mb-4">
        {Array.from({ length: stationCount }, (_, i) => (
          <button
            key={i}
            className="px-3 py-1 text-sm rounded-full border border-gray-300 text-gray-600"
          >
            Station {i + 1}
          </button>
        ))}
      </div>
      <div className="bg-gray-900 rounded-lg flex items-center justify-center h-64 text-gray-400">
        <p className="text-sm">Station 3D view · Session 4</p>
      </div>
    </div>
  );
}
