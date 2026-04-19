"use client";

/**
 * 2D DXF drawing preview rendered as SVG.
 * Uses ezdxf Python backend to convert DXF → SVG server-side.
 * Implemented in Session 2.
 */
export function DrawingPreview({ drawingId }: { drawingId: string }) {
  return (
    <div className="bg-gray-900 rounded-xl flex items-center justify-center" style={{ height: 400 }}>
      <div className="text-center text-gray-400">
        <p className="text-3xl mb-2">📐</p>
        <p className="text-sm">Drawing preview for {drawingId}</p>
        <p className="text-xs mt-1 text-gray-500">Implemented in Session 2</p>
      </div>
    </div>
  );
}
