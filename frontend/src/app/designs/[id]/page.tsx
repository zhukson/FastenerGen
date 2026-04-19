"use client";

import { use } from "react";
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

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Design {id}</h1>
          <p className="text-gray-500 text-sm">Review and approve before manufacturing</p>
        </div>
        <FeedbackButtons designId={id} />
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Left: 3D viewer (spans 2 cols) */}
        <div className="col-span-2 bg-white rounded-xl border border-gray-200 overflow-hidden" style={{ height: 480 }}>
          <ThreeDViewer designId={id} />
        </div>

        {/* Right: panels */}
        <div className="space-y-4">
          <FeaturePanel designId={id} />
          <FileDownloadPanel designId={id} />
        </div>
      </div>

      {/* Process flow */}
      <ProcessFlowDiagram designId={id} />

      {/* AI reasoning */}
      <ReasoningPanel designId={id} />
    </div>
  );
}
