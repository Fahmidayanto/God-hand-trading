import { AlertTriangle, CheckCircle2, ChevronDown, Database, FileText, Shield } from "lucide-react";

type Nullable = string | number | boolean | null | undefined;

interface LLMMSAFactor {
  factor?: string;
  current_value?: unknown;
  historical_value?: unknown;
  vector_distance?: number | null;
  factor_similarity?: number | null;
  distance_contribution?: number | null;
  available?: boolean;
}

interface LLMMSAPattern {
  rank?: number;
  id?: string;
  structure_time?: string | null;
  structure_price?: number | null;
  event_type?: string | null;
  direction?: string | null;
  session?: string | null;
  timeframe?: string | null;
  total_similarity?: number | null;
  outcome?: string | null;
  net_profit?: number | null;
  entry_time?: string | null;
  entry_price?: number | null;
  exit_time?: string | null;
  exit_price?: number | null;
  duration_minutes?: number | null;
  close_reason?: string | null;
  rejection_reason?: string | null;
  rejection_reason_code?: string | null;
}

interface LLMMSAReportData {
  conclusion?: {
    verdict?: string;
    vote?: string;
    confidence?: number | null;
    data_quality?: number | null;
    recommended_action?: string;
    mode?: string;
  };
  simple_explanation?: string;
  evidence_summary?: {
    total_patterns?: number;
    completed_patterns?: number;
    wins?: number;
    losses?: number;
    rejected?: number;
    executed_win_rate?: number | null;
    weighted_win_rate?: number | null;
    total_net_profit?: number | null;
    average_net_profit?: number | null;
  };
  top_10_patterns?: LLMMSAPattern[];
  top_3_breakdowns?: Array<{
    rank?: number;
    pattern_id?: string;
    total_similarity?: number | null;
    method?: string;
    factors?: LLMMSAFactor[];
  }>;
  closest_pattern_detail?: LLMMSAPattern | null;
  win_loss_comparison?: {
    wins?: Record<string, unknown>;
    losses?: Record<string, unknown>;
    current_pattern_comparison?: string;
    win_pattern_characteristics?: string[];
    loss_pattern_characteristics?: string[];
  };
  confirmation_and_invalidation?: {
    confirmation_conditions?: string[];
    invalidation_conditions?: string[];
    counter_scenario?: string;
  };
}

interface LLMMSAReportProps {
  report: LLMMSAReportData;
  status?: string;
}

const unavailable = "Data tidak tersedia";

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatPercent(value: unknown): string {
  const number = finiteNumber(value);
  return number === null ? unavailable : `${(number * 100).toFixed(2)}%`;
}

function formatNumber(value: unknown, digits = 4): string {
  const number = finiteNumber(value);
  return number === null ? unavailable : number.toFixed(digits);
}

function formatMoney(value: unknown): string {
  const number = finiteNumber(value);
  return number === null ? unavailable : `${number.toFixed(2)} USD`;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return unavailable;
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : unavailable;
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function formatTime(value: Nullable): string {
  if (typeof value !== "string" || !value) return unavailable;
  return value.replace("T", " ").substring(0, 19);
}

function explanationBlocks(value?: string): Array<{ label?: string; text: string }> {
  const normalized = value?.trim();
  if (!normalized) return [{ text: unavailable }];

  const lines = normalized
    .split(/\n+/)
    .map(line => line.trim())
    .filter(Boolean);
  const labeledLines = lines.map(line => {
    const match = line.match(/^(Kesimpulan|Alasan utama|Tindakan)\s*:\s*(.+)$/i);
    return match ? { label: match[1], text: match[2] } : { text: line };
  });

  if (lines.length > 1 || labeledLines.some(block => block.label)) return labeledLines;

  const sentences = normalized.match(/[^.!?]+[.!?]+|[^.!?]+$/g)?.map(sentence => sentence.trim()).filter(Boolean) ?? [];
  if (sentences.length <= 2) return [{ text: normalized }];

  const blocks: Array<{ text: string }> = [];
  for (let index = 0; index < sentences.length; index += 2) {
    blocks.push({ text: sentences.slice(index, index + 2).join(" ") });
  }
  return blocks;
}

function outcomeClass(outcome?: string | null): string {
  const normalized = outcome?.toUpperCase();
  if (normalized === "WIN") return "bg-emerald-500/10 text-emerald-600 border-emerald-500/20";
  if (normalized === "LOSS") return "bg-rose-500/10 text-rose-600 border-rose-500/20";
  if (normalized === "REJECTED") return "bg-amber-500/10 text-amber-700 border-amber-500/20";
  return "bg-slate-500/10 text-slate-600 border-slate-500/20";
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="min-w-0 border-l-2 border-blue-200 pl-3">
      <div className="text-[10px] font-semibold uppercase text-slate-500">{label}</div>
      <div className="mt-1 break-words font-mono text-sm font-bold text-slate-800">{value}</div>
    </div>
  );
}

function CharacteristicList({ items }: { items?: string[] }) {
  if (!items?.length) return <p className="text-xs text-slate-500">{unavailable}</p>;
  return (
    <ul className="space-y-1.5 text-xs text-slate-700">
      {items.map((item, index) => <li key={`${item}-${index}`}>• {item}</li>)}
    </ul>
  );
}

function ObjectMetrics({ values }: { values?: Record<string, unknown> }) {
  const entries = Object.entries(values ?? {});
  if (!entries.length) return <p className="text-xs text-slate-500">{unavailable}</p>;
  return (
    <dl className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2">
      {entries.map(([key, value]) => (
        <div key={key} className="flex min-w-0 justify-between gap-3 border-b border-blue-100 pb-1 text-xs">
          <dt className="break-words text-slate-500">{key.replace(/_/g, " ")}</dt>
          <dd className="break-all text-right font-mono font-semibold text-slate-700">{formatValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function LLMMSAReport({ report, status }: LLMMSAReportProps) {
  const conclusion = report.conclusion ?? {};
  const evidence = report.evidence_summary ?? {};
  const closest = report.closest_pattern_detail;
  const comparison = report.win_loss_comparison ?? {};
  const conditions = report.confirmation_and_invalidation ?? {};
  const simpleExplanation = explanationBlocks(report.simple_explanation);

  return (
    <section aria-labelledby="llm-msa-report-title" className="space-y-6 border-t border-blue-200 pt-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h4 id="llm-msa-report-title" className="flex items-center gap-2 text-sm font-semibold text-slate-700">
            <Database size={14} aria-hidden="true" /> Laporan LLM Market Structure
          </h4>
          <p className="mt-1 text-xs text-slate-500">Evidence historis hanya-baca. Tidak memengaruhi konsensus atau transaksi.</p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded border border-cyan-500/25 bg-cyan-500/10 px-2 py-1 text-[10px] font-bold text-cyan-700">
          <Shield size={12} aria-hidden="true" /> {conclusion.mode ?? "SHADOW"} · {status ?? "completed"}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        <Metric label="Kesimpulan" value={conclusion.verdict ?? unavailable} />
        <Metric label="Tingkat keyakinan" value={formatPercent(conclusion.confidence)} />
        <Metric label="Kualitas data" value={formatPercent(conclusion.data_quality)} />
        <Metric label="Tindakan" value={conclusion.recommended_action ?? unavailable} />
        <Metric label="Suara" value={conclusion.vote ?? unavailable} />
      </div>

      <div className="border-t border-blue-100 pt-4">
        <h5 className="mb-3 text-xs font-bold uppercase text-slate-500">Ringkasan Evidence Historis</h5>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-7">
          <Metric label="Total pola" value={evidence.total_patterns ?? 0} />
          <Metric label="WIN" value={evidence.wins ?? 0} />
          <Metric label="LOSS" value={evidence.losses ?? 0} />
          <Metric label="REJECTED" value={evidence.rejected ?? 0} />
          <Metric label="Win rate tereksekusi" value={formatPercent(evidence.executed_win_rate)} />
          <Metric label="Win rate berbobot" value={formatPercent(evidence.weighted_win_rate)} />
          <Metric label="Total Net_Profit" value={formatMoney(evidence.total_net_profit)} />
        </div>
      </div>

      <div className="border-t border-blue-100 pt-4">
        <h5 className="mb-3 text-xs font-bold uppercase text-slate-500">10 Pola Historis Teratas</h5>
        <div className="max-h-[420px] overflow-auto border-y border-blue-200">
          <table className="min-w-[980px] w-full text-left text-xs">
            <thead className="sticky top-0 bg-white text-[10px] uppercase text-slate-500">
              <tr>
                <th className="px-2 py-2">Peringkat</th><th className="px-2 py-2">Waktu struktur</th>
                <th className="px-2 py-2">Peristiwa</th><th className="px-2 py-2">Arah</th>
                <th className="px-2 py-2">Sesi</th><th className="px-2 py-2 text-right">Kemiripan</th>
                <th className="px-2 py-2">Hasil</th><th className="px-2 py-2 text-right">Net_Profit</th>
                <th className="px-2 py-2">Alasan penutupan / penolakan</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-blue-100 text-slate-700">
              {(report.top_10_patterns ?? []).map((pattern, index) => (
                <tr key={pattern.id ?? index} className="hover:bg-blue-50/60">
                  <td className="px-2 py-2 font-mono">{pattern.rank ?? index + 1}</td>
                  <td className="px-2 py-2 font-mono text-[11px]">{formatTime(pattern.structure_time)}</td>
                  <td className="px-2 py-2">{pattern.event_type ?? unavailable}</td>
                  <td className="px-2 py-2">{pattern.direction ?? unavailable}</td>
                  <td className="px-2 py-2">{pattern.session ?? unavailable}</td>
                  <td className="px-2 py-2 text-right font-mono text-cyan-700">{formatPercent(pattern.total_similarity)}</td>
                  <td className="px-2 py-2"><span className={`rounded border px-1.5 py-0.5 text-[9px] font-bold ${outcomeClass(pattern.outcome)}`}>{pattern.outcome ?? unavailable}</span></td>
                  <td className="px-2 py-2 text-right font-mono">{formatMoney(pattern.net_profit)}</td>
                  <td className="max-w-[220px] break-words px-2 py-2">{pattern.outcome?.toUpperCase() === "REJECTED" ? pattern.rejection_reason ?? pattern.rejection_reason_code ?? unavailable : pattern.close_reason ?? unavailable}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="border-t border-blue-100 pt-4">
        <h5 className="mb-3 text-xs font-bold uppercase text-slate-500">Rincian Angka Kemiripan 3 Pola Teratas</h5>
        <div className="divide-y divide-blue-100 border-y border-blue-200">
          {(report.top_3_breakdowns ?? []).map((breakdown, index) => (
            <details key={breakdown.pattern_id ?? index} className="group py-1" open={index === 0}>
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-2 py-2 text-xs font-semibold text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500">
                <span>Rank #{breakdown.rank ?? index + 1} · {breakdown.pattern_id ?? unavailable} · {formatPercent(breakdown.total_similarity)}</span>
                <ChevronDown size={14} className="shrink-0 transition-transform group-open:rotate-180" aria-hidden="true" />
              </summary>
              <div className="overflow-x-auto pb-3">
                <table className="min-w-[980px] w-full text-left text-[11px]">
                  <thead className="bg-blue-50/70 text-[10px] uppercase text-slate-500">
                    <tr><th className="px-2 py-2">Faktor</th><th className="px-2 py-2">Saat ini</th><th className="px-2 py-2">Historis</th><th className="px-2 py-2 text-right">Jarak vektor</th><th className="px-2 py-2 text-right">Kemiripan faktor</th><th className="px-2 py-2 text-right">Kontribusi jarak</th><th className="px-2 py-2">Ketersediaan</th></tr>
                  </thead>
                  <tbody className="divide-y divide-blue-100">
                    {(breakdown.factors ?? []).map((factor, factorIndex) => (
                      <tr key={`${factor.factor}-${factorIndex}`}>
                        <td className="px-2 py-2 font-semibold">{factor.factor ?? unavailable}</td>
                        <td className="max-w-[180px] break-all px-2 py-2 font-mono">{factor.available === false ? unavailable : formatValue(factor.current_value)}</td>
                        <td className="max-w-[180px] break-all px-2 py-2 font-mono">{factor.available === false ? unavailable : formatValue(factor.historical_value)}</td>
                        <td className="px-2 py-2 text-right font-mono">{factor.available === false ? unavailable : formatNumber(factor.vector_distance)}</td>
                        <td className="px-2 py-2 text-right font-mono">{factor.available === false ? unavailable : formatPercent(factor.factor_similarity)}</td>
                        <td className="px-2 py-2 text-right font-mono">{factor.available === false ? unavailable : formatNumber(factor.distance_contribution, 6)}</td>
                        <td className="px-2 py-2">{factor.available === false ? "Tidak tersedia" : "Tersedia"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          ))}
        </div>
      </div>

      <div className="border-t border-blue-100 pt-4">
        <h5 className="mb-3 text-xs font-bold uppercase text-slate-500">Detail Pola #1</h5>
        {closest ? (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            <Metric label="Waktu struktur" value={formatTime(closest.structure_time)} />
            <Metric label="Harga struktur" value={formatNumber(closest.structure_price, 2)} />
            <Metric label="Waktu entry" value={formatTime(closest.entry_time)} />
            <Metric label="Harga entry" value={formatNumber(closest.entry_price, 2)} />
            <Metric label="Waktu keluar" value={formatTime(closest.exit_time)} />
            <Metric label="Harga keluar" value={formatNumber(closest.exit_price, 2)} />
            <Metric label="Durasi" value={closest.duration_minutes == null ? unavailable : `${closest.duration_minutes} menit`} />
            <Metric label="Net_Profit" value={formatMoney(closest.net_profit)} />
            <Metric label="Alasan penutupan" value={closest.close_reason ?? unavailable} />
            <Metric label="Kemiripan" value={formatPercent(closest.total_similarity)} />
          </div>
        ) : <p className="text-xs text-slate-500">{unavailable}</p>}
      </div>

      <div className="grid grid-cols-1 gap-6 border-t border-blue-100 pt-4 lg:grid-cols-2">
        <div>
          <h5 className="mb-3 flex items-center gap-2 text-xs font-bold uppercase text-emerald-700"><CheckCircle2 size={13} aria-hidden="true" /> Karakteristik WIN</h5>
          <ObjectMetrics values={comparison.wins} />
          <div className="mt-3"><CharacteristicList items={comparison.win_pattern_characteristics} /></div>
        </div>
        <div>
          <h5 className="mb-3 flex items-center gap-2 text-xs font-bold uppercase text-rose-700"><AlertTriangle size={13} aria-hidden="true" /> Karakteristik LOSS</h5>
          <ObjectMetrics values={comparison.losses} />
          <div className="mt-3"><CharacteristicList items={comparison.loss_pattern_characteristics} /></div>
        </div>
        <p className="text-sm leading-relaxed text-slate-700 lg:col-span-2">{comparison.current_pattern_comparison ?? unavailable}</p>
      </div>

      <div className="grid grid-cols-1 gap-6 border-t border-blue-100 pt-4 lg:grid-cols-2">
        <div><h5 className="mb-3 text-xs font-bold uppercase text-emerald-700">Kondisi konfirmasi</h5><CharacteristicList items={conditions.confirmation_conditions} /></div>
        <div><h5 className="mb-3 text-xs font-bold uppercase text-rose-700">Kondisi pembatalan</h5><CharacteristicList items={conditions.invalidation_conditions} /></div>
        <div className="lg:col-span-2"><h5 className="mb-2 text-xs font-bold uppercase text-amber-700">Skenario tandingan</h5><p className="text-sm leading-relaxed text-slate-700">{conditions.counter_scenario ?? unavailable}</p></div>
      </div>

      <div className="border-t border-blue-100 pt-4">
        <h5 className="mb-2 flex items-center gap-2 text-xs font-bold uppercase text-slate-500"><FileText size={13} aria-hidden="true" /> Penjelasan Sederhana</h5>
        <div className="space-y-3 rounded-lg border-l-2 border-cyan-400 bg-blue-50/50 px-4 py-3">
          {simpleExplanation.map((block, index) => (
            <div key={`${block.label ?? "paragraf"}-${index}`} className="space-y-1">
              {block.label && <div className="text-xs font-bold text-slate-700">{block.label}</div>}
              <p className="max-w-4xl text-sm leading-6 text-slate-700">{block.text}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}