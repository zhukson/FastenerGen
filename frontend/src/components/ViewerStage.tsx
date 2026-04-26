"use client";

import { useState } from "react";
import { apiClient, type DesignResult, type OutputFile } from "@/lib/api";
import { ThreeDViewer } from "./ThreeDViewer";
import { DxfStage } from "./DxfStage";

type ViewMode = "3D" | "2D";

interface ViewerStageProps {
  designId: string;
  design: DesignResult;
  height: number;
  activeStation: number | "assembly";
  onSelectStation: (s: number | "assembly") => void;
}

const HEADER_H = 44;

function relPath(file: OutputFile, designId: string): string {
  const fp = file.file_path;
  const marker = designId + "/";
  const idx = fp.indexOf(marker);
  return idx >= 0 ? fp.slice(idx + marker.length) : fp.split("/").pop()!;
}

interface DownloadItem {
  label: string;
  file: OutputFile;
}

function buildDownloads(
  design: DesignResult,
  mode: ViewMode,
  station: number | "assembly",
): DownloadItem[] {
  const find = (type: string, sn: number | null) =>
    design.output_files.find((f) => f.file_type === type && f.station_number === sn);

  const items: DownloadItem[] = [];

  if (mode === "2D") {
    if (station === "assembly") {
      const prod = find("production_drawing", null);
      const proc = find("process_breakdown", null);
      if (prod) items.push({ label: "Production Drawing (DXF)", file: prod });
      if (proc) items.push({ label: "Process Breakdown (DXF)", file: proc });
    } else {
      const punch = find("punch_drawing", station);
      const die = find("die_drawing", station);
      if (punch) items.push({ label: `Station ${station} Punch (DXF)`, file: punch });
      if (die) items.push({ label: `Station ${station} Die (DXF)`, file: die });
    }
  } else {
    if (station === "assembly") {
      // collect any per-station assembly preview STLs
      design.output_files
        .filter((f) => f.file_type === "assembly_preview")
        .forEach((f) =>
          items.push({
            label: `Station ${f.station_number ?? "?"} Assembly (STL)`,
            file: f,
          }),
        );
    } else {
      const punchStep = find("punch_step", station);
      const punchStl = find("punch_stl", station);
      const dieStep = find("die_step", station);
      const dieStl = find("die_stl", station);
      const wpStl = find("workpiece_stl", station);
      if (punchStep) items.push({ label: `Punch (STEP)`, file: punchStep });
      if (punchStl) items.push({ label: `Punch (STL)`, file: punchStl });
      if (dieStep) items.push({ label: `Die (STEP)`, file: dieStep });
      if (dieStl) items.push({ label: `Die (STL)`, file: dieStl });
      if (wpStl) items.push({ label: `Workpiece (STL)`, file: wpStl });
    }
  }
  return items;
}

export function ViewerStage({
  designId,
  design,
  height,
  activeStation,
  onSelectStation,
}: ViewerStageProps) {
  const [mode, setMode] = useState<ViewMode>("3D");
  const [menuOpen, setMenuOpen] = useState(false);

  const stations = design.process_plan.stations.map((s) => s.station_number);
  const downloads = buildDownloads(design, mode, activeStation);

  const handleDownload = (file: OutputFile) => {
    window.open(apiClient.downloadFile(designId, relPath(file, designId)), "_blank");
    setMenuOpen(false);
  };

  const stageBodyH = height - HEADER_H;

  return (
    <div className="w-full flex flex-col bg-gray-900" style={{ height }}>
      {/* Header bar: mode toggle + station tabs + download */}
      <div
        className="flex items-center gap-2 px-3 bg-gray-800 border-b border-gray-700 flex-shrink-0"
        style={{ height: HEADER_H }}
      >
        {/* Mode toggle */}
        <div className="inline-flex rounded-md border border-gray-600 overflow-hidden">
          {(["3D", "2D"] as ViewMode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`px-3 py-1 text-xs font-semibold transition-colors ${
                mode === m
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-gray-200 hover:bg-gray-700"
              }`}
            >
              {m}
            </button>
          ))}
        </div>

        {/* Station tabs */}
        <div className="flex items-center gap-1 ml-2 overflow-x-auto">
          {stations.map((sn) => (
            <button
              key={sn}
              onClick={() => onSelectStation(sn)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors whitespace-nowrap ${
                activeStation === sn
                  ? "bg-blue-600 text-white"
                  : "text-gray-400 hover:text-gray-200 hover:bg-gray-700"
              }`}
            >
              Station {sn}
            </button>
          ))}
          <button
            onClick={() => onSelectStation("assembly")}
            className={`px-2.5 py-1 rounded text-xs font-medium transition-colors whitespace-nowrap ${
              activeStation === "assembly"
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:text-gray-200 hover:bg-gray-700"
            }`}
          >
            All Stations
          </button>
        </div>

        {/* Download menu */}
        <div className="relative ml-auto">
          <button
            onClick={() => setMenuOpen((v) => !v)}
            disabled={downloads.length === 0}
            className="flex items-center gap-1 px-3 py-1 rounded text-xs font-medium bg-gray-700 hover:bg-gray-600 text-gray-100 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-3.5 w-3.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5m0 0l5-5m-5 5V4"
              />
            </svg>
            Download
          </button>
          {menuOpen && downloads.length > 0 && (
            <>
              {/* Click-away catcher */}
              <div
                className="fixed inset-0 z-10"
                onClick={() => setMenuOpen(false)}
              />
              <div className="absolute right-0 mt-1 w-60 z-20 bg-gray-800 border border-gray-600 rounded-md shadow-xl py-1">
                {downloads.map((d, i) => (
                  <button
                    key={i}
                    onClick={() => handleDownload(d.file)}
                    className="w-full text-left px-3 py-1.5 text-xs text-gray-200 hover:bg-gray-700 flex items-center justify-between gap-2"
                  >
                    <span className="truncate">{d.label}</span>
                    <span className="text-gray-500 font-mono uppercase shrink-0">
                      {d.file.format}
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 relative overflow-hidden">
        {mode === "3D" ? (
          <ThreeDViewer
            designId={designId}
            design={design}
            height={stageBodyH}
            activeStation={activeStation}
            onSelectStation={onSelectStation}
            hideStationTabs
          />
        ) : (
          <DxfStage
            designId={designId}
            design={design}
            activeStation={activeStation}
            height={stageBodyH}
          />
        )}
      </div>
    </div>
  );
}
