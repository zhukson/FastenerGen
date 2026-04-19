"use client";

export default function DesignsPage() {
  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">Generated Designs</h1>
      <p className="text-gray-500 mb-6">
        Review and approve generated die designs before sending to manufacturing.
      </p>

      <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
        <p className="text-4xl mb-3">⚙</p>
        <p className="font-medium">No designs yet</p>
        <p className="text-sm mt-1">
          <a href="/upload" className="text-blue-600 hover:underline">
            Upload a drawing
          </a>{" "}
          to get started.
        </p>
      </div>
    </div>
  );
}
