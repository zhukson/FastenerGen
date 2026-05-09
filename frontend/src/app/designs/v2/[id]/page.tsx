"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { apiClient, type V2DesignDetail } from "@/lib/api";

export default function V2DesignDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [data, setData] = useState<V2DesignDetail | null>(null);
  const [reasoning, setReasoning] = useState<string>("");
  const [gongReview, setGongReview] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const detail = await apiClient.v2GetDesign(id);
        if (cancelled) return;
        setData(detail);
        const [md, gr] = await Promise.all([
          fetch(apiClient.v2ReasoningUrl(id)).then((r) => r.text()),
          fetch(apiClient.v2GongReviewUrl(id))
            .then((r) => (r.ok ? r.text() : ""))
            .catch(() => ""),
        ]);
        if (!cancelled) {
          setReasoning(md);
          setGongReview(gr);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) {
    return (
      <main className="max-w-5xl mx-auto p-6">
        <p className="text-red-600">Error: {error}</p>
        <Link href="/upload" className="text-blue-600 underline text-sm">
          ← back
        </Link>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="max-w-5xl mx-auto p-6">
        <p className="text-gray-500">Loading v2 design {id}…</p>
      </main>
    );
  }

  const pf = data.process_forming;
  const confidenceColor =
    data.confidence === "high"
      ? "text-green-600 bg-green-50 border-green-200"
      : data.confidence === "medium"
        ? "text-amber-600 bg-amber-50 border-amber-200"
        : "text-red-600 bg-red-50 border-red-200";

  return (
    <main className="max-w-6xl mx-auto p-6 space-y-6">
      <header>
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs text-gray-400 uppercase tracking-wide">
              v2 过模图 (process forming drawing)
            </p>
            <h1 className="text-2xl font-semibold mt-0.5">{pf.part_name_zh}</h1>
            <p className="text-sm text-gray-500 mt-1">
              {pf.material} · {pf.stations.length} 工位 · drawing_id{" "}
              <code className="text-xs">{data.drawing_id}</code>
            </p>
          </div>
          <span
            className={`px-2.5 py-1 rounded-full text-xs font-medium border ${confidenceColor}`}
          >
            confidence: {data.confidence}
          </span>
        </div>
      </header>

      {/* Cited cases */}
      {data.cited_case_ids.length > 0 && (
        <section className="bg-blue-50 border border-blue-100 rounded-lg p-4">
          <p className="text-xs font-medium text-blue-700 mb-2">
            Cited reference cases (Tier 1 经验库)
          </p>
          <ul className="space-y-1">
            {data.cited_case_ids.map((cid) => (
              <li key={cid} className="text-sm font-mono text-blue-800">
                · {cid}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Gong-style free-form engineering review (P1.5) */}
      {gongReview && gongReview.trim() && !gongReview.includes("did not emit") && (
        <section className="bg-amber-50 border border-amber-200 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <p className="text-sm font-semibold text-amber-800">
              龚茂良式工艺审查 / Gong-style Engineering Review
            </p>
            <span className="text-[10px] uppercase tracking-wide bg-amber-200 text-amber-900 px-2 py-0.5 rounded-full">
              free-form analysis
            </span>
          </div>
          <p className="text-xs text-amber-700 mb-3">
            LLM 在写 JSON 之前用龚茂良视角的自由分析 — 涵盖特征反查、工位推导、物理风险、材料专项、案例选择
          </p>
          <pre className="text-xs text-gray-800 whitespace-pre-wrap font-sans leading-relaxed bg-white/60 rounded-lg p-3 border border-amber-100">
            {gongReview}
          </pre>
        </section>
      )}

      {/* DXF preview */}
      <section className="bg-gray-900 rounded-xl overflow-hidden border border-gray-800">
        <div className="px-4 py-2 flex justify-between items-center border-b border-gray-800">
          <p className="text-xs text-gray-400">过模图 preview</p>
          <a
            href={apiClient.v2DxfUrl(id)}
            className="text-xs text-blue-400 hover:text-blue-300 underline"
            download
          >
            download .dxf
          </a>
        </div>
        <img
          src={apiClient.v2PreviewUrl(id)}
          alt="过模图 preview"
          className="w-full bg-gray-900"
        />
      </section>

      {/* Stations table */}
      <section className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-4 py-2 border-b border-gray-100">
          <p className="text-sm font-medium text-gray-700">工位概览 / Station overview</p>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-500">
            <tr>
              <th className="text-left px-4 py-2 font-medium w-12">#</th>
              <th className="text-left px-4 py-2 font-medium">操作 / Operation</th>
              <th className="text-left px-4 py-2 font-medium">工件类型</th>
              <th className="text-right px-4 py-2 font-medium">L (mm)</th>
              <th className="text-right px-4 py-2 font-medium">D (mm)</th>
              <th className="text-left px-4 py-2 font-medium">备注</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            <tr className="bg-gray-50/40">
              <td className="px-4 py-2 text-gray-500">0</td>
              <td className="px-4 py-2 text-gray-500 italic">blank / 下料</td>
              <td className="px-4 py-2">{pf.blank.type}</td>
              <td className="px-4 py-2 text-right font-mono">{pf.blank.overall_length_mm}</td>
              <td className="px-4 py-2 text-right font-mono">{pf.blank.max_diameter_mm}</td>
              <td className="px-4 py-2 text-gray-500">{pf.blank.notes_zh ?? ""}</td>
            </tr>
            {pf.stations.map((st) => (
              <tr key={st.n}>
                <td className="px-4 py-2 font-medium">{st.n}</td>
                <td className="px-4 py-2 font-mono text-xs">{st.operation}</td>
                <td className="px-4 py-2">{st.workpiece.type}</td>
                <td className="px-4 py-2 text-right font-mono">{st.workpiece.overall_length_mm}</td>
                <td className="px-4 py-2 text-right font-mono">{st.workpiece.max_diameter_mm}</td>
                <td className="px-4 py-2 text-gray-600 max-w-md truncate" title={st.notes_zh ?? ""}>
                  {st.notes_zh ?? ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Verification */}
      <section className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-4 py-2 border-b border-gray-100 flex items-center justify-between">
          <p className="text-sm font-medium text-gray-700">规则校验 / Rule checks</p>
          <span
            className={
              data.verification.passed
                ? "text-xs text-green-700 bg-green-50 border border-green-200 rounded-full px-2 py-0.5"
                : "text-xs text-red-700 bg-red-50 border border-red-200 rounded-full px-2 py-0.5"
            }
          >
            {data.verification.passed ? "passed" : "needs review"}
          </span>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-500">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Check</th>
              <th className="text-left px-4 py-2 font-medium w-24">Severity</th>
              <th className="text-left px-4 py-2 font-medium w-24">Result</th>
              <th className="text-left px-4 py-2 font-medium">Message</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data.verification.checks.map((check) => (
              <tr key={check.check_name}>
                <td className="px-4 py-2 font-mono text-xs">{check.check_name}</td>
                <td className="px-4 py-2">{check.severity}</td>
                <td className="px-4 py-2">{check.passed ? "pass" : "review"}</td>
                <td className="px-4 py-2 text-gray-600">{check.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Reasoning */}
      {reasoning && (
        <section className="bg-white border border-gray-200 rounded-xl p-5">
          <p className="text-sm font-medium text-gray-700 mb-3">
            设计理由 / Reasoning
          </p>
          <pre className="text-xs text-gray-700 whitespace-pre-wrap font-sans leading-relaxed">
            {reasoning}
          </pre>
        </section>
      )}

      {/* Downloads */}
      <section className="flex gap-3 text-sm">
        <a
          href={apiClient.v2DxfUrl(id)}
          download
          className="px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          ⬇ process_forming.dxf
        </a>
        <a
          href={apiClient.v2ParametersUrl(id)}
          download
          className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
        >
          ⬇ process_parameters.json
        </a>
        <a
          href={apiClient.v2ReasoningUrl(id)}
          download
          className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
        >
          ⬇ design_reasoning.md
        </a>
      </section>

      {pf.post_processes.length > 0 && (
        <p className="text-sm text-gray-500">
          后处理 / Post-processes: {pf.post_processes.join(", ")}
        </p>
      )}
    </main>
  );
}
