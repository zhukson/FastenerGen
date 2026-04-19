"use client";

/**
 * Displays structured PartFeatures extracted from the product drawing.
 * Data binding implemented in Session 3 when API is available.
 */
export function FeaturePanel({ designId }: { designId: string }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <h2 className="font-semibold text-sm mb-3">Extracted Features</h2>
      <div className="space-y-2 text-sm text-gray-500">
        <FeatureRow label="Part No." value="—" />
        <FeatureRow label="Type" value="—" />
        <FeatureRow label="Material" value="—" />
        <FeatureRow label="Grade" value="—" />
        <FeatureRow label="Thread" value="—" />
        <FeatureRow label="Length" value="—" />
      </div>
      <p className="text-xs text-gray-400 mt-3">Populated in Session 3</p>
    </div>
  );
}

function FeatureRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-400">{label}</span>
      <span className="font-mono text-xs text-gray-700">{value}</span>
    </div>
  );
}
