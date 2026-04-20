"use client";

import type { ProcessPlan } from "@/lib/api";

interface ProcessFlowDiagramProps {
  designId: string;
  plan?: ProcessPlan;
}

const OP_ICONS: Record<string, string> = {
  upsetting: "⬆",
  heading: "⚙",
  forward_extrusion: "→",
  backward_extrusion: "←",
  combined: "⚙",
  trimming: "✂",
  piercing: "⬇",
};

export function ProcessFlowDiagram({ designId: _designId, plan }: ProcessFlowDiagramProps) {
  if (!plan) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold mb-2">Process Flow</h2>
        <p className="text-sm text-gray-400">Loading...</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold">Process Flow</h2>
        <span className="text-xs text-gray-400 font-mono">
          blank ⌀{plan.blank_diameter}×{plan.blank_length}mm
        </span>
      </div>

      <div className="flex items-start gap-2 overflow-x-auto pb-2">
        {/* Wire stock node */}
        <StationNode
          icon="🔩"
          label="Wire Stock"
          sublabel={`⌀${plan.blank_diameter}mm`}
          detail={`L=${plan.blank_length}mm`}
          variant="blank"
        />
        <Arrow />

        {plan.stations.map((station, i) => (
          <div key={station.station_number} className="flex items-start gap-2">
            <StationNode
              icon={OP_ICONS[station.operation] ?? "⚙"}
              label={`Station ${station.station_number}`}
              sublabel={station.operation.replace("_", " ")}
              detail={
                station.upset_ratio != null
                  ? `D/d=${station.upset_ratio.toFixed(2)}`
                  : station.output_shape.head_diameter != null
                  ? `head⌀${station.output_shape.head_diameter}`
                  : ""
              }
              variant="station"
            />
            {i < plan.stations.length - 1 && <Arrow />}
          </div>
        ))}

        {plan.post_processes.length > 0 && (
          <>
            <Arrow />
            {plan.post_processes.map((pp, i) => (
              <div key={pp} className="flex items-start gap-2">
                <StationNode
                  icon="🔄"
                  label={pp.replace("_", " ")}
                  sublabel="post-process"
                  detail=""
                  variant="post"
                />
                {i < plan.post_processes.length - 1 && <Arrow />}
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}

function StationNode({
  icon,
  label,
  sublabel,
  detail,
  variant,
}: {
  icon: string;
  label: string;
  sublabel: string;
  detail: string;
  variant: "blank" | "station" | "post";
}) {
  const ring =
    variant === "blank"
      ? "border-gray-300 bg-gray-50"
      : variant === "post"
      ? "border-orange-300 bg-orange-50"
      : "border-blue-300 bg-blue-50";

  return (
    <div className="flex flex-col items-center gap-1 min-w-[72px]">
      <div
        className={`w-12 h-12 rounded-full border-2 flex items-center justify-center text-lg ${ring}`}
      >
        {icon}
      </div>
      <p className="text-xs font-medium text-center leading-tight">{label}</p>
      <p className="text-xs text-gray-400 text-center leading-tight">{sublabel}</p>
      {detail && (
        <p className="text-xs text-gray-300 font-mono text-center leading-tight">{detail}</p>
      )}
    </div>
  );
}

function Arrow() {
  return (
    <div className="flex items-center pt-4">
      <span className="text-gray-300 text-xl">→</span>
    </div>
  );
}
