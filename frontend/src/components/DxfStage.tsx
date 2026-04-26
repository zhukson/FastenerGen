"use client";

import { useState } from "react";
import { apiClient, type DesignResult, type OutputFile } from "@/lib/api";

interface DxfStageProps {
  designId: string;
  design: DesignResult;
  activeStation: number | "assembly";
  height: number;
}

function relPath(file: OutputFile, designId: string): string {
  const fp = file.file_path;
  const marker = designId + "/";
  const idx = fp.indexOf(marker);
  return idx >= 0 ? fp.slice(idx + marker.length) : fp.split("/").pop()!;
}

function findFile(
  design: DesignResult,
  fileType: string,
  station: number | null,
): OutputFile | undefined {
  return design.output_files.find(
    (f) => f.file_type === fileType && f.station_number === station,
  );
}

export function DxfStage({ designId, design, activeStation, height }: DxfStageProps) {
  if (activeStation === "assembly") {
    const production = findFile(design, "production_drawing", null);
    if (!production) {
      return <Empty height={height} message="No production drawing available." />;
    }
    return (
      <div className="w-full overflow-auto bg-gray-900" style={{ height }}>
        <DxfImage
          designId={designId}
          file={production}
          caption="Production Drawing"
        />
      </div>
    );
  }

  const punch = findFile(design, "punch_drawing", activeStation);
  const die = findFile(design, "die_drawing", activeStation);

  if (!punch && !die) {
    return <Empty height={height} message={`No DXF drawings for station ${activeStation}.`} />;
  }

  return (
    <div className="w-full overflow-auto bg-gray-900 p-3 space-y-3" style={{ height }}>
      {punch && (
        <DxfImage
          designId={designId}
          file={punch}
          caption={`Station ${activeStation} — Punch Drawing`}
        />
      )}
      {die && (
        <DxfImage
          designId={designId}
          file={die}
          caption={`Station ${activeStation} — Die Drawing`}
        />
      )}
    </div>
  );
}

function DxfImage({
  designId,
  file,
  caption,
}: {
  designId: string;
  file: OutputFile;
  caption: string;
}) {
  const [error, setError] = useState(false);
  const url = apiClient.dxfPreview(designId, relPath(file, designId));

  return (
    <div className="rounded-lg overflow-hidden border border-gray-700 bg-gray-950">
      <div className="px-3 py-1.5 bg-gray-800 text-gray-300 text-xs font-medium border-b border-gray-700">
        {caption}
      </div>
      {error ? (
        <div className="p-4 text-xs text-red-400">
          Preview unavailable — download the DXF to view in CAD software.
        </div>
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={url}
          alt={caption}
          className="w-full block"
          crossOrigin="anonymous"
          onError={() => setError(true)}
          loading="lazy"
        />
      )}
    </div>
  );
}

function Empty({ height, message }: { height: number; message: string }) {
  return (
    <div
      className="w-full flex items-center justify-center bg-gray-900 text-gray-500 text-sm"
      style={{ height }}
    >
      {message}
    </div>
  );
}
