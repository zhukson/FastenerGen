"use client";

import { useState } from "react";
import type { ProcessPlan, RetrievedCase, VerificationResult } from "@/lib/api";

interface ReasoningPanelProps {
  designId: string;
  plan?: ProcessPlan;
  retrievedCases?: RetrievedCase[];
  confidence?: string;
  verification?: VerificationResult;
}

const CONF_COLORS: Record<string, string> = {
  high: "bg-green-100 text-green-700",
  medium: "bg-yellow-100 text-yellow-700",
  low: "bg-red-100 text-red-700",
};

export function ReasoningPanel({
  designId: _designId,
  plan,
  retrievedCases = [],
  confidence = "—",
  verification,
}: ReasoningPanelProps) {
  const [showCases, setShowCases] = useState(false);
  const [showChecks, setShowChecks] = useState(false);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">AI Design Reasoning</h2>
        <ConfidenceBadge level={confidence} />
      </div>

      {/* Process reasoning */}
      {plan && (
        <section>
          <h3 className="text-sm font-medium text-gray-700 mb-1">Process Planning Summary</h3>
          <p className="text-sm text-gray-600 leading-relaxed">{plan.reasoning_summary}</p>
          <div className="mt-2 flex gap-2 flex-wrap">
            <Tag label={`${plan.total_stations} stations`} />
            <Tag label={`Blank ⌀${plan.blank_diameter}×${plan.blank_length}mm`} />
            {plan.post_processes.map((p) => (
              <Tag key={p} label={p.replace("_", " ")} variant="orange" />
            ))}
          </div>
        </section>
      )}

      {/* Verification summary */}
      {verification && (
        <section>
          <button
            onClick={() => setShowChecks((v) => !v)}
            className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900"
          >
            <span
              className={`w-4 h-4 rounded-full flex items-center justify-center text-xs text-white ${verification.passed ? "bg-green-500" : "bg-red-500"}`}
            >
              {verification.passed ? "✓" : "✗"}
            </span>
            Verification ({verification.checks.filter((c) => c.passed).length}/
            {verification.checks.length} checks passed)
            <span className="text-gray-400">{showChecks ? "▲" : "▼"}</span>
          </button>
          {showChecks && (
            <div className="mt-2 space-y-1">
              {verification.checks.map((c) => (
                <div key={c.check_name} className="flex items-start gap-2 text-xs">
                  <span className={c.passed ? "text-green-500" : "text-red-500"}>
                    {c.passed ? "✓" : "✗"}
                  </span>
                  <span className="text-gray-500 font-mono">{c.check_name}</span>
                  <span className="text-gray-600">{c.message}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Similar cases */}
      {retrievedCases.length > 0 && (
        <section>
          <button
            onClick={() => setShowCases((v) => !v)}
            className="text-sm font-medium text-gray-700 hover:text-gray-900 flex items-center gap-1"
          >
            Similar Cases Used ({retrievedCases.length})
            <span className="text-gray-400">{showCases ? "▲" : "▼"}</span>
          </button>
          {showCases && (
            <div className="mt-2 space-y-2">
              {retrievedCases.map((rc) => (
                <div
                  key={rc.case.case_id}
                  className="text-xs border border-gray-100 rounded-lg p-3 bg-gray-50"
                >
                  <div className="font-medium text-gray-700">
                    {rc.case.part_features.description}
                  </div>
                  <div className="text-gray-500 mt-0.5">
                    {rc.case.part_features.thread.spec} ·{" "}
                    {rc.case.part_features.material_grade} ·{" "}
                    {rc.case.process_plan.total_stations} stations
                  </div>
                  <div className="text-gray-400 mt-0.5">
                    Similarity: {((rc.rerank_score ?? rc.vector_similarity) * 100).toFixed(0)}% ·
                    Confidence:{" "}
                    <span
                      className={`font-medium ${rc.case.confidence === "high" ? "text-green-600" : "text-yellow-600"}`}
                    >
                      {rc.case.confidence}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function ConfidenceBadge({ level }: { level: string }) {
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium ${CONF_COLORS[level] ?? "bg-gray-100 text-gray-500"}`}
    >
      {level} confidence
    </span>
  );
}

function Tag({
  label,
  variant = "blue",
}: {
  label: string;
  variant?: "blue" | "orange";
}) {
  const colors =
    variant === "blue"
      ? "bg-blue-50 text-blue-700 border-blue-100"
      : "bg-orange-50 text-orange-700 border-orange-100";
  return (
    <span className={`px-2 py-0.5 rounded border text-xs font-mono ${colors}`}>{label}</span>
  );
}
