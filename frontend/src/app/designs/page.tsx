"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiClient, type DesignSummary } from "@/lib/api";

const CONFIDENCE_COLORS: Record<string, string> = {
  high: "bg-green-100 text-green-700",
  medium: "bg-yellow-100 text-yellow-700",
  low: "bg-red-100 text-red-700",
};

const STATUS_COLORS: Record<string, string> = {
  completed: "text-green-600",
  flagged: "text-yellow-600",
  failed: "text-red-600",
  pending: "text-gray-400",
  processing: "text-blue-600",
};

export default function DesignsPage() {
  const [designs, setDesigns] = useState<DesignSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .listDesigns()
      .then(setDesigns)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto">
        <h1 className="text-2xl font-bold mb-6">Generated Designs</h1>
        <div className="text-gray-400 text-sm">Loading...</div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Generated Designs</h1>
          <p className="text-gray-500 text-sm mt-1">
            Review and approve generated die designs before sending to manufacturing.
          </p>
        </div>
        <Link
          href="/upload"
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
        >
          + New Design
        </Link>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {designs.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
          <p className="text-4xl mb-3">⚙</p>
          <p className="font-medium">No designs yet</p>
          <p className="text-sm mt-1">
            <Link href="/upload" className="text-blue-600 hover:underline">
              Upload a drawing
            </Link>{" "}
            to get started.
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Part</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Thread</th>
                <th className="text-right px-4 py-3 font-medium text-gray-600">Length</th>
                <th className="text-right px-4 py-3 font-medium text-gray-600">Stations</th>
                <th className="text-center px-4 py-3 font-medium text-gray-600">Confidence</th>
                <th className="text-center px-4 py-3 font-medium text-gray-600">Status</th>
                <th className="text-right px-4 py-3 font-medium text-gray-600">3D</th>
                <th className="text-right px-4 py-3 font-medium text-gray-600">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {designs.map((d) => (
                <tr
                  key={d.design_id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => (window.location.href = `/designs/${d.design_id}`)}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{d.description}</div>
                    {d.part_number && (
                      <div className="text-xs text-gray-400 font-mono">{d.part_number}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-700">{d.thread_spec}</td>
                  <td className="px-4 py-3 text-right text-gray-600">{d.overall_length}mm</td>
                  <td className="px-4 py-3 text-right text-gray-600">{d.station_count}</td>
                  <td className="px-4 py-3 text-center">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${CONFIDENCE_COLORS[d.confidence] ?? "bg-gray-100 text-gray-500"}`}
                    >
                      {d.confidence}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className={`text-xs font-medium ${STATUS_COLORS[d.status] ?? "text-gray-400"}`}>
                      {d.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">{d.has_3d ? "✓" : "—"}</td>
                  <td className="px-4 py-3 text-right text-gray-400 text-xs">
                    {new Date(d.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
