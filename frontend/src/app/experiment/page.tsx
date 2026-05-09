"use client";

import { useState } from "react";
import { apiClient, type M14ExperimentResponse } from "@/lib/api";

export default function ExperimentPage() {
  const [qualityMode, setQualityMode] = useState(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<M14ExperimentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const res = await apiClient.runM14Experiment({
        qualityMode,
        selfConsistencyRuns: qualityMode ? 3 : 1,
      });
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Experiment failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Experiment</h1>
        <p className="mt-2 text-sm text-gray-500">
          DIN912 M14 leave-one-out: use only page 1 product drawing as input, keep
          the page 3 forming-process drawing withheld, then generate a new 过模图.
        </p>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-5">
        <div className="grid gap-3 text-sm sm:grid-cols-3">
          <Info label="Input" value="Page 1 product drawing only" />
          <Info label="Held out" value="BD19046-P03-DIN912-M14-P2-0" />
          <Info label="Runtime cases" value="8 DWG + 3 standards + textbooks" />
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          <ReferenceImage
            title="Input Seen by LLM"
            subtitle="Product drawing, page 1 only"
            src={apiClient.m14InputPreviewUrl()}
          />
          <ReferenceImage
            title="Withheld Answer"
            subtitle="Factory forming-process drawing, page 3, not sent to LLM"
            src={apiClient.m14GroundTruthPreviewUrl()}
          />
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={qualityMode}
              onChange={(e) => setQualityMode(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300"
            />
            High quality mode
          </label>
          <span className="text-xs text-gray-400">
            {qualityMode
              ? "Opus, 3 vision runs, 3 design candidates, retry, Step 3 image"
              : "Sonnet, 1 vision run, 1 design candidate, no Step 3 image"}
          </span>
        </div>

        <div className="mt-5 flex flex-wrap gap-3">
          <button
            onClick={run}
            disabled={running}
            className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {running ? "Running…" : "Run M14 Test"}
          </button>
          <a
            href={apiClient.m14InputPdfUrl()}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
          >
            Input PDF
          </a>
          <a
            href={apiClient.m14GroundTruthPdfUrl()}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
          >
            Withheld Answer PDF
          </a>
          <a
            href={apiClient.m14GroundTruthDxfUrl()}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
          >
            Structured GT DXF
          </a>
        </div>
      </div>

      {running && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700">
          Running the full pipeline. Cheap mode should avoid the previous multi-candidate cost spike.
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
          {error}
        </div>
      )}

      {result && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-5">
          <p className="text-sm font-medium text-green-800">Experiment complete</p>
          <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
            <Info label="Design ID" value={result.design_id} />
            <Info label="Stations" value={String(result.station_count)} />
            <Info label="Confidence" value={result.confidence} />
            <Info label="Folder" value={result.experiment_folder} />
          </div>
          <div className="mt-4 flex flex-wrap gap-3">
            <a
              href={`/designs/v2/${result.design_id}`}
              className="rounded-lg bg-green-700 px-4 py-2 text-sm font-medium text-white hover:bg-green-800"
            >
              Open Result
            </a>
            <a
              href={apiClient.v2DxfUrl(result.design_id)}
              className="rounded-lg border border-green-300 px-4 py-2 text-sm text-green-800 hover:bg-green-100"
            >
              Generated DXF
            </a>
            <a
              href={apiClient.m14GroundTruthPdfUrl()}
              className="rounded-lg border border-green-300 px-4 py-2 text-sm text-green-800 hover:bg-green-100"
            >
              Withheld Answer PDF
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

function ReferenceImage({
  title,
  subtitle,
  src,
}: {
  title: string;
  subtitle: string;
  src: string;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-gray-50">
      <div className="border-b border-gray-200 bg-white px-3 py-2">
        <p className="text-sm font-medium text-gray-800">{title}</p>
        <p className="text-xs text-gray-500">{subtitle}</p>
      </div>
      <img src={src} alt={title} className="h-auto w-full bg-white" />
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
      <p className="mt-1 break-words font-mono text-sm text-gray-800">{value}</p>
    </div>
  );
}
