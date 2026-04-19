"use client";

import { Suspense } from "react";

/**
 * 3D viewer for die assembly STL files.
 * Uses @react-three/fiber + @react-three/drei.
 * Full STL loading + STEP support via occt-import-js implemented in Session 4.
 */
export function ThreeDViewer({ designId }: { designId: string }) {
  return (
    <div className="w-full h-full flex items-center justify-center bg-gray-900 text-gray-400">
      <div className="text-center">
        <p className="text-4xl mb-3">🔩</p>
        <p className="font-medium">3D Viewer</p>
        <p className="text-sm mt-1 text-gray-500">
          Design {designId} · STL viewer implemented in Session 4
        </p>
      </div>
    </div>
  );
}
