"use client";

import type { PartFeatures } from "@/lib/api";

interface FeaturePanelProps {
  designId: string;
  features?: PartFeatures;
}

export function FeaturePanel({ designId: _designId, features }: FeaturePanelProps) {
  if (!features) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <h2 className="font-semibold text-sm mb-3">Extracted Features</h2>
        <p className="text-xs text-gray-400">Loading...</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <h2 className="font-semibold text-sm mb-3">Extracted Features</h2>
      <div className="space-y-1.5 text-sm">
        <FeatureRow label="Part No." value={features.part_number ?? "—"} />
        <FeatureRow label="Type" value={features.head.type} />
        <FeatureRow label="Material" value={features.material_grade} />
        <FeatureRow label="Grade" value={features.strength_grade} />
        <FeatureRow label="Thread" value={features.thread.spec} />
        <FeatureRow label="Length" value={`${features.overall_length}mm`} />
        <FeatureRow label="Head ⌀" value={`${features.head.diameter}mm`} />
        <FeatureRow label="Shank ⌀" value={`${features.shank.diameter}mm`} />
        {features.surface_treatment && (
          <FeatureRow label="Surface" value={features.surface_treatment} />
        )}
        {features.standard && (
          <FeatureRow label="Standard" value={features.standard} />
        )}
        {features.core_hardness_min_hrc && (
          <FeatureRow
            label="Core HRC"
            value={`${features.core_hardness_min_hrc}–${features.core_hardness_max_hrc}`}
          />
        )}
      </div>
    </div>
  );
}

function FeatureRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-gray-400 shrink-0">{label}</span>
      <span className="font-mono text-xs text-gray-700 text-right truncate" title={value}>
        {value}
      </span>
    </div>
  );
}
