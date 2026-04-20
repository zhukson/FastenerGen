"use client";

import { use, useEffect, useState } from "react";
import { apiClient, type DesignResult } from "@/lib/api";
import { ThreeDViewer } from "@/components/ThreeDViewer";
import { FeaturePanel } from "@/components/FeaturePanel";
import { ReasoningPanel } from "@/components/ReasoningPanel";
import { FileDownloadPanel } from "@/components/FileDownloadPanel";
import { FeedbackButtons } from "@/components/FeedbackButtons";
import { ProcessFlowDiagram } from "@/components/ProcessFlowDiagram";

export default function DesignDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [design, setDesign] = useState<DesignResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .getDesign(id)
      .then(setDesign)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto">
        <div className="text-gray-400 text-sm p-8">Loading design...</div>
      </div>
    );
  }

  if (error || !design) {
    return (
      <div className="max-w-7xl mx-auto p-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          {error ?? "Design not found"}
        </div>
      </div>
    );
  }

  const CONF_COLORS: Record<string, string> = {
    high: "bg-green-100 text-green-700",
    medium: "bg-yellow-100 text-yellow-700",
    low: "bg-red-100 text-red-700",
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{design.part_features.description}</h1>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-gray-500 text-sm font-mono">
              {design.part_features.thread.spec} · L={design.part_features.overall_length}mm
            </span>
            <span
              className={`px-2 py-0.5 rounded text-xs font-medium ${CONF_COLORS[design.confidence] ?? "bg-gray-100 text-gray-500"}`}
            >
              {design.confidence} confidence
            </span>
            {design.verification.flagged_for_review && (
              <span className="px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">
                needs review
              </span>
            )}
          </div>
        </div>
        <FeedbackButtons designId={id} />
      </div>

      {/* Main layout: 3D viewer (left 60%) + panels (right 40%) */}
      <div className="grid grid-cols-5 gap-6">
        {/* 3D Viewer */}
        <div
          className="col-span-3 bg-white rounded-xl border border-gray-200 overflow-hidden"
          style={{ height: 500 }}
        >
          <ThreeDViewer designId={id} design={design} />
        </div>

        {/* Right panels */}
        <div className="col-span-2 space-y-4">
          <FeaturePanel designId={id} features={design.part_features} />
          <FileDownloadPanel designId={id} files={design.output_files} />
        </div>
      </div>

      {/* Process flow */}
      <ProcessFlowDiagram designId={id} plan={design.process_plan} />

      {/* AI reasoning */}
      <ReasoningPanel
        designId={id}
        plan={design.process_plan}
        retrievedCases={design.retrieved_cases}
        confidence={design.confidence}
        verification={design.verification}
      />

      {/* Cost / metadata footer */}
      <div className="text-xs text-gray-400 flex gap-4">
        <span>Design ID: {design.design_id}</span>
        <span>LLM cost: ${design.llm_cost_usd.toFixed(4)}</span>
        <span>Retries: {design.verification.retry_count}</span>
        <span>Created: {new Date(design.created_at).toLocaleString()}</span>
      </div>
    </div>
  );
}
