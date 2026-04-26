"use client";

import React, { useEffect, useRef } from "react";
import { type DesignResult, type ShapeDescription } from "@/lib/api";

// ---------------------------------------------------------------------------
// Helper: map operation enum to readable label
// ---------------------------------------------------------------------------

function getOperationLabel(design: DesignResult, stationNumber: number): string {
  const station = design.process_plan.stations.find(s => s.station_number === stationNumber);
  if (!station) return "";
  return station.operation
    .replace(/_/g, " ")
    .replace(/\b\w/g, c => c.toUpperCase());
}

// ---------------------------------------------------------------------------
// Cross-section drawing from ShapeDescription
// ---------------------------------------------------------------------------

type Point = [number, number]; // [r, z]

function buildProfile(shape: ShapeDescription): Point[] {
  const L = shape.overall_length;
  const shankR = (shape.shank_diameter ?? shape.max_diameter) / 2;
  const headR = shape.head_diameter ? shape.head_diameter / 2 : shankR;
  const headH = shape.head_height ?? 0;

  const pts: Point[] = [];
  pts.push([shankR, 0]);

  if (headR > shankR * 1.05 && headH > 0.1) {
    const shankTop = L - headH;
    pts.push([shankR, Math.max(0.1, shankTop)]);
    pts.push([headR, Math.max(0.1, shankTop)]);
    pts.push([headR, L]);
  } else {
    pts.push([shankR, L]);
  }

  return pts;
}

function drawCrossSection(
  canvas: HTMLCanvasElement,
  shape: ShapeDescription,
) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const w = canvas.width;
  const h = canvas.height;

  // Background
  ctx.fillStyle = "#111827";
  ctx.fillRect(0, 0, w, h);

  const profile = buildProfile(shape);
  const L = shape.overall_length;
  const maxR = Math.max(...profile.map(([r]) => r));

  if (maxR === 0 || L === 0) return;

  const padX = 10;
  const padY = 8;
  const scaleX = (w / 2 - padX) / maxR;
  const scaleY = (h - 2 * padY) / L;
  const scale = Math.min(scaleX, scaleY);

  const cx = w / 2;
  const bottom = h - padY;

  const px = (r: number) => cx + r * scale;
  const py = (z: number) => bottom - z * scale;

  // Filled cross-section
  ctx.fillStyle = "#f59e0b";
  ctx.beginPath();
  ctx.moveTo(cx, bottom); // bottom axis

  for (const [r, z] of profile) {
    ctx.lineTo(px(r), py(z));
  }
  // Top axis point
  const [, lastZ] = profile[profile.length - 1];
  ctx.lineTo(cx, py(lastZ));
  // Mirror left side
  for (let i = profile.length - 1; i >= 0; i--) {
    const [r, z] = profile[i];
    ctx.lineTo(cx - r * scale, py(z));
  }
  ctx.closePath();
  ctx.fill();

  // Outline stroke
  ctx.strokeStyle = "#b45309";
  ctx.lineWidth = 1;
  ctx.stroke();

  // Center axis line (dashed)
  ctx.strokeStyle = "#4b5563";
  ctx.lineWidth = 0.8;
  ctx.setLineDash([3, 2]);
  ctx.beginPath();
  ctx.moveTo(cx, padY - 2);
  ctx.lineTo(cx, h - padY + 2);
  ctx.stroke();
  ctx.setLineDash([]);
}

// ---------------------------------------------------------------------------
// WorkpieceCrossSection thumbnail
// ---------------------------------------------------------------------------

function WorkpieceCrossSection({
  shape,
  active,
  onClick,
  label,
}: {
  shape: ShapeDescription;
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (canvasRef.current) drawCrossSection(canvasRef.current, shape);
  }, [shape]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div
      onClick={onClick}
      className={`flex flex-col items-center cursor-pointer rounded-lg p-1 transition-colors flex-shrink-0 ${
        active ? "bg-blue-900 ring-2 ring-blue-400" : "hover:bg-gray-800"
      }`}
    >
      <canvas
        ref={canvasRef}
        width={90}
        height={110}
        className="rounded"
      />
      <p className="text-xs text-gray-400 mt-1 text-center leading-tight max-w-[90px] truncate">
        {label}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// StationViewer — Process Story strip
// ---------------------------------------------------------------------------

export function StationViewer({
  design,
  activeStation,
  onSelectStation,
}: {
  design: DesignResult;
  designId: string;
  activeStation: number | "assembly";
  onSelectStation: (s: number | "assembly") => void;
}) {
  // Blank shape (station 0) — synthesized from plan blank dimensions
  const blankShape: ShapeDescription = {
    overall_length: design.process_plan.blank_length,
    max_diameter: design.process_plan.blank_diameter,
    head_diameter: null,
    head_height: null,
    shank_diameter: design.process_plan.blank_diameter,
    shank_length: null,
  };

  return (
    <div className="flex items-end gap-2 overflow-x-auto py-3 px-1">
      {/* Station 0 — blank */}
      <WorkpieceCrossSection
        shape={blankShape}
        active={activeStation === 0}
        onClick={() => onSelectStation(0)}
        label="Blank"
      />

      {/* Arrow */}
      <span className="text-gray-600 flex-shrink-0 mb-8 select-none">›</span>

      {/* Stations 1..N — intermediate shapes */}
      {design.process_plan.stations.map((station, i) => (
        <React.Fragment key={station.station_number}>
          <WorkpieceCrossSection
            shape={station.output_shape}
            active={activeStation === station.station_number}
            onClick={() => onSelectStation(station.station_number)}
            label={`S${station.station_number} ${getOperationLabel(design, station.station_number)}`}
          />
          {i < design.process_plan.stations.length - 1 && (
            <span className="text-gray-600 flex-shrink-0 mb-8 select-none">›</span>
          )}
        </React.Fragment>
      ))}

      {/* All Stations overview */}
      <span className="text-gray-600 flex-shrink-0 mb-8 select-none">›</span>
      <div
        onClick={() => onSelectStation("assembly")}
        className={`flex flex-col items-center cursor-pointer rounded-lg p-1 transition-colors flex-shrink-0 ${
          activeStation === "assembly" ? "bg-blue-900 ring-2 ring-blue-400" : "hover:bg-gray-800"
        }`}
      >
        <div
          className="rounded bg-gray-800 flex items-center justify-center"
          style={{ width: 90, height: 110 }}
        >
          <div className="flex gap-1 items-end">
            {[0.4, 0.6, 0.5, 0.8].map((h, i) => (
              <div
                key={i}
                className="bg-amber-500 rounded-sm w-3"
                style={{ height: `${h * 60}px` }}
              />
            ))}
          </div>
        </div>
        <p className="text-xs text-gray-400 mt-1 text-center leading-tight">All Stations</p>
      </div>
    </div>
  );
}
