"use client";

export default function EvalPage() {
  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">Evaluation Dashboard</h1>
      <p className="text-gray-500 mb-6">
        Track pipeline quality metrics and regression against golden test cases.
      </p>

      <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
        <p className="text-4xl mb-3">📊</p>
        <p className="font-medium">No eval data yet</p>
        <p className="text-sm mt-1">Evaluation pipeline implemented in Session 5.</p>
      </div>
    </div>
  );
}
