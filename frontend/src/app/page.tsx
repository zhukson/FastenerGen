"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";

export default function DashboardPage() {
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: () => apiClient.health(),
    refetchInterval: 30_000,
  });

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-3xl font-bold mb-2">FastenerGPT</h1>
      <p className="text-gray-500 mb-8">
        Upload a fastener drawing and generate one editable 过模图 DXF.
      </p>

      {/* Status cards */}
      <div className="grid grid-cols-2 gap-4 mb-8 sm:grid-cols-4">
        <StatusCard label="API" value={health?.status ?? "…"} ok={health?.status === "ok"} />
        <StatusCard label="Designs" value="0" />
        <StatusCard label="Tier 1 Cases" value="11" />
        <StatusCard label="Textbook Refs" value="27+" />
      </div>

      {/* Quick actions */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold mb-4">Quick Start</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <ActionCard
            href="/upload"
            title="Upload Drawing"
            description="Generate a process-forming drawing from PDF, DWG, DXF, or image"
            icon="↑"
          />
          <ActionCard
            href="/designs"
            title="View Designs"
            description="Review generated DXF outputs, reasoning, and cited cases"
            icon="⚙"
          />
          <ActionCard
            href="/experiment"
            title="Experiment"
            description="Run the DIN912 M14 leave-one-out demo with the held-out answer key"
            icon="◎"
          />
        </div>
      </div>
    </div>
  );
}

function StatusCard({
  label,
  value,
  ok,
}: {
  label: string;
  value: string;
  ok?: boolean;
}) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <p
        className={`mt-1 text-xl font-semibold ${
          ok === true ? "text-green-600" : ok === false ? "text-red-500" : "text-gray-900"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

function ActionCard({
  href,
  title,
  description,
  icon,
}: {
  href: string;
  title: string;
  description: string;
  icon: string;
}) {
  return (
    <a
      href={href}
      className="flex gap-4 rounded-lg border border-gray-200 p-4 hover:border-blue-400 hover:bg-blue-50 transition-colors"
    >
      <span className="text-2xl">{icon}</span>
      <div>
        <p className="font-medium">{title}</p>
        <p className="text-sm text-gray-500">{description}</p>
      </div>
    </a>
  );
}
