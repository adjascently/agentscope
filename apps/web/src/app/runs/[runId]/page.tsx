
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  Activity, ArrowLeft, ArrowUpRight, CheckCircle2,
  CircleAlert, Clock3, ExternalLink, GitBranch,
  Layers3, Terminal, Zap
} from "lucide-react";
import ThemeToggle from "../../theme-toggle";

export const instant = false;

type Span = {
  span_id: string;
  run_id: string;
  parent_span_id: string | null;
  name: string;
  span_type: string;
  status: string;
  timestamp: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

type TraceResponse = {
  run_id: string;
  span_count: number;
  spans: Span[];
};

type Diagnosis = {
  code: string;
  title: string;
  explanation: string;
  suggested_fix: string;
  evidence: {
    span_id: string;
    span_name: string;
    error_message: string;
  };
};

type DiagnosisResponse = {
  run_id: string;
  status: string;
  diagnosis_count: number;
  diagnoses: Diagnosis[];
};

const API = process.env.AGENTSCOPE_API_URL ?? "http://api:8000";

async function getTrace(runId: string): Promise<TraceResponse> {
  const response = await fetch(
    `${API}/v1/traces/${encodeURIComponent(runId)}`,
    { cache: "no-store" }
  );

  if (response.status === 404) notFound();
  if (!response.ok) throw new Error("Unable to load trace");

  return response.json();
}

async function getDiagnosis(
  runId: string
): Promise<DiagnosisResponse | null> {
  try {
    const response = await fetch(
      `${API}/v1/runs/${encodeURIComponent(runId)}/diagnosis`,
      { cache: "no-store" }
    );

    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

function duration(span: Span): number {
  const value = span.metadata?.latency_ms;
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.max(0, value);
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return Math.max(0, parsed);
  }
  return 0;
}

function formatDuration(ms: number) {
  return ms >= 1000
    ? `${(ms / 1000).toFixed(2)} s`
    : `${ms.toFixed(0)} ms`;
}

function color(span: Span) {
  if (span.status === "error") return "#e4777d";
  if (span.span_type === "agent") return "#8b93a7";
  if (span.span_type === "llm") return "#7779c9";
  if (span.span_type === "tool") return "#3b9b8c";
  return "#94a3b8";
}

function buildTimeline(spans: Span[]) {
  const map = new Map(spans.map(s => [s.span_id, s]));
  const children = new Map<string, Span[]>();
  const roots: Span[] = [];

  for (const span of spans) {
    const parent = span.parent_span_id;
    if (parent && parent !== span.span_id && map.has(parent)) {
      const group = children.get(parent) ?? [];
      group.push(span);
      children.set(parent, group);
    } else {
      roots.push(span);
    }
  }

  const sort = (a: Span, b: Span) =>
    new Date(a.timestamp).getTime() -
    new Date(b.timestamp).getTime();

  roots.sort(sort);
  for (const group of children.values()) group.sort(sort);

  const result: { span: Span; depth: number }[] = [];
  const visited = new Set<string>();

  function visit(span: Span, depth: number) {
    if (visited.has(span.span_id)) return;
    visited.add(span.span_id);
    result.push({ span, depth });

    for (const child of children.get(span.span_id) ?? []) {
      visit(child, depth + 1);
    }
  }

  roots.forEach(s => visit(s, 0));
  spans.forEach(s => visit(s, 0));

  return result;
}

function ExecutionTimeline({ spans }: { spans: Span[] }) {
  if (!spans.length) return null;

  const timeline = buildTimeline(spans);
  const start = Math.min(
    ...spans.map(s => new Date(s.timestamp).getTime())
  );
  const end = Math.max(
    ...spans.map(s => new Date(s.timestamp).getTime() + duration(s))
  );
  const total = Math.max(1, end - start);
  const failed = spans.filter(s => s.status === "error").length;

  return (
    <section className="trace-panel overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--trace-border)] p-6 md:p-8">
        <div>
          <div className="trace-eyebrow flex items-center gap-2">
            <Activity size={16} />
            EXECUTION WATERFALL
          </div>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight">
            Execution Timeline
          </h2>
          <p className="trace-muted mt-2 text-base">
            {spans.length} spans · {failed} errors · {formatDuration(total)}
          </p>
        </div>

        <span className={`trace-status ${failed ? "trace-error" : "trace-success"}`}>
          {failed ? <CircleAlert size={16} /> : <CheckCircle2 size={16} />}
          {failed ? "Errors detected" : "Execution successful"}
        </span>
      </div>

      <div className="flex flex-wrap gap-x-6 gap-y-3 px-6 pt-6 text-sm md:px-8">
        {[
          ["Agent", "#8b93a7"],
          ["LLM", "#7779c9"],
          ["Tool", "#3b9b8c"],
          ["Error", "#e4777d"],
        ].map(([label, shade]) => (
          <span key={label} className="trace-muted flex items-center gap-2">
            <span
              className="h-3 w-3 rounded"
              style={{ backgroundColor: shade }}
            />
            {label}
          </span>
        ))}
      </div>

      <div className="overflow-x-auto px-6 py-7 md:px-8">
        <div className="min-w-[760px]">
          <div className="trace-muted grid grid-cols-[minmax(220px,0.9fr)_minmax(320px,2fr)_100px] gap-5 border-b border-[var(--trace-border)] pb-4 text-xs font-semibold uppercase tracking-wider">
            <span>Operation</span>
            <div className="flex justify-between">
              {[0, 25, 50, 75, 100].map(n => (
                <span key={n}>
                  {((total * n) / 100000).toFixed(1)}s
                </span>
              ))}
            </div>
            <span className="text-right">Duration</span>
          </div>

          <div className="mt-4 space-y-1">
            {timeline.map(({ span, depth }, index) => {
              const ms = duration(span);
              const left =
                ((new Date(span.timestamp).getTime() - start) / total) * 100;
              const width = (ms / total) * 100;

              return (
                <a
                  key={span.span_id}
                  href={`#span-${span.span_id}`}
                  className="trace-timeline-row grid grid-cols-[minmax(220px,0.9fr)_minmax(320px,2fr)_100px] items-center gap-5 rounded-lg px-3 py-3"
                >
                  <div
                    className="min-w-0"
                    style={{ paddingLeft: Math.min(depth, 5) * 16 }}
                  >
                    <div className="flex items-center gap-2">
                      {depth > 0 && (
                        <span className="trace-muted">↳</span>
                      )}
                      <span className="truncate text-[15px] font-medium">
                        {span.name}
                      </span>
                    </div>
                    <div className="trace-muted mt-1 text-xs">
                      #{index + 1} · {span.span_type}
                      {depth > 0 ? ` · level ${depth}` : " · root"}
                    </div>
                  </div>

                  <div className="trace-track relative h-8 overflow-hidden rounded-md">
                    {[0, 25, 50, 75, 100].map(n => (
                      <span
                        key={n}
                        className="trace-gridline absolute top-0 h-full border-l"
                        style={{ left: `${n}%` }}
                      />
                    ))}
                    <span
                      className="absolute top-[9px] h-[14px] rounded"
                      style={{
                        left: `${Math.max(0, left)}%`,
                        width: `${Math.min(width, 100 - Math.max(0, left))}%`,
                        minWidth: 4,
                        backgroundColor: color(span),
                      }}
                    />
                  </div>

                  <span className="trace-muted text-right font-mono text-sm">
                    {formatDuration(ms)}
                  </span>
                </a>
              );
            })}
          </div>
        </div>
      </div>

      <p className="trace-muted px-6 pb-7 text-sm md:px-8">
        Select an operation to jump to its span details.
        Indentation represents recorded parent-child relationships.
      </p>
    </section>
  );
}

function FailureDiagnosis({
  result,
}: {
  result: DiagnosisResponse | null;
}) {
  if (!result?.diagnoses?.length) return null;

  return (
    <section className="trace-panel mb-6 overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-[var(--trace-border)] bg-[#fff5f5] px-5 py-4 dark:bg-[#39252e]">
        <div className="flex items-center gap-2 font-semibold text-[#c73b49] dark:text-[#ff858e]">
          <CircleAlert size={19} />
          <span>Failure Diagnosis</span>
        </div>
        <span className="trace-muted text-sm">
          {result.diagnosis_count} {result.diagnosis_count === 1 ? "finding" : "findings"}
        </span>
      </div>

      <div className="divide-y divide-[var(--trace-border)]">
        {result.diagnoses.map(d => (
          <article
            key={`${d.code}-${d.evidence.span_id}`}
            className="px-5 py-4 md:px-6"
          >
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#fff0f1] text-[#e04455] dark:bg-[#472b36] dark:text-[#ff858e]">
                <CircleAlert size={23} />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-base font-semibold leading-snug">
                  {d.title}
                </h3>
                <p className="trace-muted mt-1 text-sm leading-relaxed">
                  {d.explanation}
                </p>
              </div>
            </div>

            <div className="mt-4 border-t border-[var(--trace-border)] pt-3">
              <p className="trace-eyebrow text-xs">SUGGESTED FIX</p>
              <p className="mt-1.5 text-sm leading-relaxed">
                {d.suggested_fix}
              </p>
            </div>

            <div className="mt-4 border-t border-[var(--trace-border)] pt-3">
              <a
                href={`#span-${d.evidence.span_id}`}
                className="trace-link inline-flex items-center gap-2 text-sm font-medium hover:underline"
              >
                View evidence: {d.evidence.span_name}
                <ArrowUpRight size={15} />
              </a>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function SpanDetails({ spans }: { spans: Span[] }) {
  return (
    <section className="mt-6">
      <div className="mb-5">
        <div className="trace-eyebrow">TRACE INSPECTION</div>
        <h2 className="mt-2 text-2xl font-semibold">Span Details</h2>
        <p className="trace-muted mt-2 text-base">
          Inspect recorded metadata for each operation.
        </p>
      </div>

      <div className="grid items-start gap-5 xl:grid-cols-2">
        {spans.map((span, index) => (
          <article
            id={`span-${span.span_id}`}
            key={span.span_id}
            className="trace-panel scroll-mt-8 overflow-hidden"
          >
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--trace-border)] p-6">
              <div className="min-w-0">
                <p className="trace-eyebrow">
                  SPAN {index + 1} / {span.span_type.toUpperCase()}
                </p>
                <h3 className="mt-2 break-words text-xl font-semibold">
                  {span.name}
                </h3>
              </div>

              <span className={`trace-status ${
                span.status === "error" ? "trace-error" : "trace-success"
              }`}>
                {span.status === "error"
                  ? <CircleAlert size={14} />
                  : <CheckCircle2 size={14} />}
                {span.status}
              </span>
            </div>

            <div className="grid gap-5 p-6 sm:grid-cols-2">
              <div>
                <p className="trace-muted text-sm">Timestamp</p>
                <p className="mt-2 text-[15px]">
                  {new Date(span.timestamp).toLocaleString()}
                </p>
              </div>
              <div>
                <p className="trace-muted text-sm">Duration</p>
                <p className="mt-2 font-mono text-[15px]">
                  {formatDuration(duration(span))}
                </p>
              </div>
              <div>
                <p className="trace-muted text-sm">Span ID</p>
                <p className="mt-2 break-all font-mono text-sm">
                  {span.span_id}
                </p>
              </div>
              <div>
                <p className="trace-muted text-sm">Parent span</p>
                <p className="mt-2 break-all font-mono text-sm">
                  {span.parent_span_id ?? "Root span"}
                </p>
              </div>
            </div>

            <details className="group border-t border-[var(--trace-border)]">
              <summary className="trace-details-summary flex cursor-pointer items-center justify-between px-6 py-4 text-base font-medium">
                <span className="flex items-center gap-2">
                  <Terminal size={17} />
                  View Raw Metadata
                </span>
                <span className="trace-muted text-sm group-open:hidden">
                  Expand +
                </span>
                <span className="trace-muted hidden text-sm group-open:inline">
                  Collapse −
                </span>
              </summary>

              <div className="px-6 pb-6">
                <pre className="trace-code overflow-x-auto rounded-lg p-5 font-mono text-[13px] leading-6">
                  {JSON.stringify(span.metadata ?? {}, null, 2)}
                </pre>
              </div>
            </details>
          </article>
        ))}
      </div>
    </section>
  );
}

export default async function RunDetailPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;

  const [trace, diagnosis] = await Promise.all([
    getTrace(runId),
    getDiagnosis(runId),
  ]);

  const failed = trace.spans.filter(s => s.status === "error").length;
  const totalTokens = trace.spans.reduce((sum, span) => {
    const input = Number(span.metadata?.input_tokens ?? 0);
    const output = Number(span.metadata?.output_tokens ?? 0);
    return sum +
      (Number.isFinite(input) ? input : 0) +
      (Number.isFinite(output) ? output : 0);
  }, 0);

  return (
    <div className="trace-page min-h-screen">
      <style>{`
        .trace-page {
          --trace-bg: #f7f8fb;
          --trace-surface: #ffffff;
          --trace-inset: #f3f5f9;
          --trace-text: #202433;
          --trace-muted: #657084;
          --trace-border: #dfe4ed;
          --trace-track: #e9edf5;
          --trace-link: #5657b8;
          background: var(--trace-bg);
          color: var(--trace-text);
        }
        html.dark .trace-page {
          --trace-bg: #0d1017;
          --trace-surface: #171b25;
          --trace-inset: #1e2430;
          --trace-text: #edf0f6;
          --trace-muted: #a0aabd;
          --trace-border: #303747;
          --trace-track: #252d3a;
          --trace-link: #a6a6ff;
        }
        .trace-panel {
          background: var(--trace-surface);
          border: 1px solid var(--trace-border);
          border-radius: 16px;
        }
        .trace-muted { color: var(--trace-muted); }
        .trace-eyebrow {
          color: var(--trace-link);
          font-size: 12px;
          font-weight: 700;
          letter-spacing: .12em;
        }
        .trace-link { color: var(--trace-link); }
        .trace-inset { background: var(--trace-inset); }
        .trace-track { background: var(--trace-track); }
        .trace-gridline { border-color: var(--trace-border); }
        .trace-timeline-row:hover,
        .trace-details-summary:hover {
          background: var(--trace-inset);
        }
        .trace-code {
          background: var(--trace-inset);
          color: var(--trace-text);
        }
        .trace-status {
          display: inline-flex;
          align-items: center;
          gap: 7px;
          padding: 7px 12px;
          border-radius: 999px;
          font-size: 13px;
          font-weight: 600;
        }
        .trace-error {
          color: #d96d77;
          background: rgba(220, 85, 100, .10);
        }
        .trace-success {
          color: #299b79;
          background: rgba(40, 170, 130, .10);
        }
        html.dark .trace-success { color: #69d2aa; }
      `}</style>

      <header className="sticky top-0 z-20 border-b border-[var(--trace-border)] bg-[var(--trace-surface)]">
        <div className="flex min-h-[60px] items-center justify-between gap-4 px-6 md:px-10">
          <Link href="/" className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#7374ca] text-white">
              <Activity size={22} />
            </span>
            <span className="text-lg font-bold tracking-tight">
              AgentScope
            </span>
          </Link>

          <div className="flex items-center gap-3">
            <Link
              href="/#runs"
              className="trace-link hidden items-center gap-2 text-sm font-medium sm:flex"
            >
              <ArrowLeft size={16} />
              All runs
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1100px] px-5 py-5 md:px-8 lg:px-10">
        <div className="mb-5">
          <Link
            href="/#runs"
            className="trace-link inline-flex items-center gap-2 text-sm font-medium"
          >
            <ArrowLeft size={15} />
            Back to Executions
          </Link>

          <div className="mt-4 flex flex-wrap items-start justify-between gap-5">
            <div className="min-w-0">
              <p className="trace-eyebrow flex items-center gap-2">
                <GitBranch size={15} />
                TRACE EXPLORER
              </p>

              <h1 className="mt-3 text-3xl font-semibold tracking-tight md:text-3xl">
                Execution Details
              </h1>

              <p className="trace-muted mt-3 break-all font-mono text-sm md:text-base">
                {trace.run_id}
              </p>
            </div>

            <span className={`trace-status ${
              failed ? "trace-error" : "trace-success"
            }`}>
              {failed ? <CircleAlert size={16} /> : <CheckCircle2 size={16} />}
              {failed ? "Errors detected" : "All spans successful"}
            </span>
          </div>
        </div>

        <div className="mb-5 grid gap-3 sm:grid-cols-3">
          {[
            { label: "Recorded Spans", value: trace.span_count, icon: Layers3 },
            { label: "Error Spans", value: failed, icon: CircleAlert },
            { label: "Recorded Tokens", value: totalTokens.toLocaleString(), icon: Zap },
          ].map(metric => (
            <div key={metric.label} className="trace-panel p-4">
              <div className="trace-muted flex items-center justify-between text-sm">
                {metric.label}
                <metric.icon size={19} />
              </div>
              <div className="mt-2 text-2xl font-semibold tracking-tight">
                {metric.value}
              </div>
            </div>
          ))}
        </div>

        <FailureDiagnosis result={diagnosis} />
        <ExecutionTimeline spans={trace.spans} />
        <SpanDetails spans={trace.spans} />
      </main>

      <footer className="mt-6 border-t border-[var(--trace-border)]">
        <div className="trace-muted mx-auto flex w-full max-w-[1100px] flex-wrap items-center justify-between gap-4 px-6 py-7 text-sm md:px-10">
          <span>AgentScope · AI agent observability</span>
          <a
            href="https://github.com/adjascently/agentscope"
            target="_blank"
            rel="noopener noreferrer"
            className="trace-link flex items-center gap-2"
          >
            GitHub <ExternalLink size={15} />
          </a>
        </div>
      </footer>
    </div>
  );
}
