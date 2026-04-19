"use client";

/**
 * Visual diagram of the forming station sequence.
 * Shows intermediate workpiece shapes (icons) connected by arrows.
 * Full data binding implemented in Session 3.
 */
export function ProcessFlowDiagram({ designId }: { designId: string }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h2 className="font-semibold mb-4">Process Flow</h2>
      <div className="flex items-center gap-3 overflow-x-auto pb-2">
        <StationNode label="Wire Stock" sublabel="⌀? × ?mm" isBlank />
        <Arrow />
        <StationNode label="Station 1" sublabel="Pre-form" />
        <Arrow />
        <StationNode label="Station 2" sublabel="Heading" />
        <Arrow />
        <StationNode label="Thread Roll" sublabel="Post-process" isPost />
      </div>
      <p className="text-xs text-gray-400 mt-4">Real station data populated in Session 3</p>
    </div>
  );
}

function StationNode({
  label,
  sublabel,
  isBlank,
  isPost,
}: {
  label: string;
  sublabel: string;
  isBlank?: boolean;
  isPost?: boolean;
}) {
  return (
    <div className="flex flex-col items-center gap-1 min-w-[80px]">
      <div
        className={`w-14 h-14 rounded-full border-2 flex items-center justify-center text-xl
        ${isBlank ? "border-gray-300 bg-gray-50" : isPost ? "border-orange-300 bg-orange-50" : "border-blue-300 bg-blue-50"}`}
      >
        {isBlank ? "🔩" : isPost ? "🔄" : "⚙"}
      </div>
      <p className="text-xs font-medium text-center">{label}</p>
      <p className="text-xs text-gray-400 text-center">{sublabel}</p>
    </div>
  );
}

function Arrow() {
  return <span className="text-gray-300 text-xl shrink-0">→</span>;
}
