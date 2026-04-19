"use client";

/**
 * Displays the AI design reasoning (PseudoReasoning + ProcessPlan notes).
 * Highlights confidence level prominently — low confidence is flagged in red.
 * Data binding implemented in Session 3.
 */
export function ReasoningPanel({ designId }: { designId: string }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold">AI Design Reasoning</h2>
        <ConfidenceBadge level="—" />
      </div>
      <p className="text-sm text-gray-400">
        AI reasoning display implemented in Session 3 when design pipeline is available.
      </p>
    </div>
  );
}

function ConfidenceBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    high: "bg-green-100 text-green-700",
    medium: "bg-yellow-100 text-yellow-700",
    low: "bg-red-100 text-red-700",
    "—": "bg-gray-100 text-gray-500",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[level] ?? colors["—"]}`}>
      {level} confidence
    </span>
  );
}
