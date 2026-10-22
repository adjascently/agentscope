
import Link from "next/link";
import { notFound } from "next/navigation";

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

type TimelineSpan = {
  span: Span;
  depth: number;
};

async function getTrace(runId: string): Promise<TraceResponse> {
  const apiBaseUrl =
    process.env.AGENTSCOPE_API_URL ??
    "http://127.0.0.1:8000";

  const response = await fetch(
    `${apiBaseUrl}/v1/traces/${encodeURIComponent(runId)}`,
    { cache: "no-store" }
  );

  if (response.status === 404) {
    notFound();
  }

  if (!response.ok) {
    throw new Error("Failed to load trace");
  }

  return response.json();
}

function getDuration(span: Span): number {
  const value = span.metadata.latency_ms;

  return typeof value === "number" && Number.isFinite(value)
    ? Math.max(0, value)
    : 0;
}

function getSpanColor(span: Span): string {
  if (span.status === "error") return "bg-rose-500";

  switch (span.span_type) {
    case "agent":
      return "bg-indigo-400";
    case "llm":
      return "bg-violet-400";
    case "tool":
      return "bg-sky-400";
    default:
      return "bg-slate-400";
  }
}

function buildTimeline(spans: Span[]): TimelineSpan[] {
  const spanMap = new Map(
    spans.map((span) => [span.span_id, span])
  );

  const children = new Map<string, Span[]>();
  const roots: Span[] = [];

  for (const span of spans) {
    const parentId = span.parent_span_id;

    if (
      parentId &&
      parentId !== span.span_id &&
      spanMap.has(parentId)
    ) {
      const siblings = children.get(parentId) ?? [];
      siblings.push(span);
      children.set(parentId, siblings);
    } else {
      roots.push(span);
    }
  }

  const sortByTime = (a: Span, b: Span) =>
    new Date(a.timestamp).getTime() -
    new Date(b.timestamp).getTime();

  roots.sort(sortByTime);

  for (const siblings of children.values()) {
    siblings.sort(sortByTime);
  }

  const result: TimelineSpan[] = [];
  const visited = new Set<string>();

  function visit(span: Span, depth: number) {
    if (visited.has(span.span_id)) return;

    visited.add(span.span_id);
    result.push({ span, depth });

    for (const child of children.get(span.span_id) ?? []) {
      visit(child, depth + 1);
    }
  }

  for (const root of roots) {
    visit(root, 0);
  }

  // Keep malformed or cyclic records visible rather than dropping them.
  for (const span of spans) {
    visit(span, 0);
  }

  return result;
}

function ExecutionWaterfall({ spans }: { spans: Span[] }) {
  if (spans.length === 0) return null;

  const timeline = buildTimeline(spans);

  const startTime = Math.min(
    ...spans.map((span) => new Date(span.timestamp).getTime())
  );

  const endTime = Math.max(
    ...spans.map(
      (span) =>
        new Date(span.timestamp).getTime() + getDuration(span)
    )
  );

  const totalDuration = Math.max(endTime - startTime, 1);

  const ticks = Array.from({ length: 5 }, (_, index) => ({
    position: index * 25,
    label: `${((totalDuration * index) / 4000).toFixed(1)}s`,
  }));

  const rootSpan = timeline.find(
    ({ span, depth }) =>
      depth === 0 &&
      typeof span.metadata.agent_name === "string"
  );

  const agentName = rootSpan?.span.metadata.agent_name;

  const failedSpans = spans.filter(
    (span) => span.status === "error"
  );

  return (
    <section className="mb-10 overflow-hidden rounded-xl border border-slate-800 bg-[#101522] p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-widest text-indigo-400">
            Execution Timeline
          </p>

          <h2 className="mt-2 text-xl font-semibold">
            {typeof agentName === "string"
              ? agentName
              : "Agent Execution"}
          </h2>

          <p className="mt-2 text-sm text-slate-400">
            {spans.length} spans ·{" "}
            {failedSpans.length} errors ·{" "}
            {(totalDuration / 1000).toFixed(2)}s timeline
          </p>
        </div>

        <span
          className={
            failedSpans.length > 0
              ? "rounded-full bg-rose-500/10 px-3 py-1 text-xs font-medium text-rose-400"
              : "rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400"
          }
        >
          {failedSpans.length > 0
            ? "● Error detected"
            : "● All spans OK"}
        </span>
      </div>

      <div className="mt-6 flex flex-wrap gap-4 text-xs text-slate-400">
        <span>🟪 Agent</span>
        <span>🟣 LLM</span>
        <span>🔵 Tool</span>
        <span>🔴 Error</span>
      </div>

      <div className="mt-8 overflow-x-auto">
        <div className="min-w-[700px]">
          <div className="grid grid-cols-[220px_minmax(0,1fr)_90px] items-center gap-4 border-b border-slate-800 pb-3 text-xs uppercase tracking-wide text-slate-500">
            <span>Operation</span>

            <div className="relative h-5">
              {ticks.map((tick) => (
                <span
                  key={tick.position}
                  className="absolute whitespace-nowrap"
                  style={{
                    left: `${tick.position}%`,
                    transform:
                      tick.position === 0
                        ? "translateX(0)"
                        : tick.position === 100
                          ? "translateX(-100%)"
                          : "translateX(-50%)",
                  }}
                >
                  {tick.label}
                </span>
              ))}
            </div>

            <span className="text-right">Duration</span>
          </div>

          <div className="mt-3 space-y-2">
            {timeline.map(({ span, depth }, index) => {
              const timestamp = new Date(
                span.timestamp
              ).getTime();

              const duration = getDuration(span);

              const left =
                ((timestamp - startTime) / totalDuration) * 100;

              const width =
                (duration / totalDuration) * 100;

              return (
                <a
                  key={span.span_id}
                  href={`#span-${span.span_id}`}
                  className="grid grid-cols-[220px_minmax(0,1fr)_90px] items-center gap-4 rounded-lg px-1 py-2 transition-colors hover:bg-slate-800/50"
                >
                  <div className="min-w-0">
                    <div
                      className="flex min-w-0 items-center gap-2"
                      style={{
                        paddingLeft: `${Math.min(depth, 5) * 16}px`,
                      }}
                    >
                      {depth > 0 && (
                        <span className="shrink-0 text-slate-600">
                          ↳
                        </span>
                      )}

                      <p
                        className={`truncate text-sm font-medium ${
                          span.status === "error"
                            ? "text-rose-400"
                            : "text-slate-200"
                        }`}
                        title={span.name}
                      >
                        {span.name}
                      </p>
                    </div>

                    <p
                      className="mt-1 text-xs text-slate-500"
                      style={{
                        paddingLeft: `${Math.min(depth, 5) * 16}px`,
                      }}
                    >
                      #{index + 1} · {span.span_type}
                      {depth > 0 ? ` · level ${depth}` : " · root"}
                    </p>
                  </div>

                  <div className="relative h-8 overflow-hidden rounded bg-slate-900/50">
                    {[0, 25, 50, 75, 100].map(
                      (position) => (
                        <div
                          key={position}
                          className="absolute top-0 h-full border-l border-slate-700/50"
                          style={{ left: `${position}%` }}
                        />
                      )
                    )}

                    <div
                      title={`${span.name}: ${duration}ms`}
                      className={`absolute top-2 h-4 rounded-sm ${getSpanColor(span)}`}
                      style={{
                        left: `${left}%`,
                        width: `${width}%`,
                        minWidth: "3px",
                      }}
                    />
                  </div>

                  <span
                    className={`text-right font-mono text-xs ${
                      span.status === "error"
                        ? "text-rose-400"
                        : "text-slate-400"
                    }`}
                  >
                    {duration.toFixed(1)}ms
                  </span>
                </a>
              );
            })}
          </div>
        </div>
      </div>

      {failedSpans.map((span) => (
        <div
          key={span.span_id}
          className="mt-6 rounded-lg border border-rose-900/60 bg-rose-950/20 p-4"
        >
          <p className="text-sm font-semibold text-rose-400">
            ✕ {span.name} failed
          </p>

          <p className="mt-2 text-sm text-rose-200/80">
            {typeof span.metadata.error_message === "string"
              ? span.metadata.error_message
              : "An error occurred during execution."}
          </p>
        </div>
      ))}

      <p className="mt-5 text-xs text-slate-500">
        Click a timeline row to jump to its span details.
        Indentation represents recorded parent-child relationships.
      </p>
    </section>
  );
}

export const instant = false;

export default async function RunDetailPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;
  const trace = await getTrace(runId);

  return (
    <main className="min-h-screen bg-[#080b12] text-white">
      <div className="mx-auto max-w-5xl px-6 py-12">
        <Link
          href="/"
          className="text-sm text-indigo-400 hover:text-indigo-300"
        >
          ← Back to Dashboard
        </Link>

        <header className="mb-10 mt-8">
          <h1 className="text-3xl font-bold">
            Trace Details
          </h1>

          <p className="mt-3 break-all font-mono text-sm text-slate-400">
            {trace.run_id}
          </p>

          <p className="mt-3 text-sm text-slate-400">
            {trace.span_count} execution span(s)
          </p>
        </header>

        <ExecutionWaterfall spans={trace.spans} />

        <h2 className="mb-5 text-xl font-semibold">
          Span Details
        </h2>

        <section className="space-y-4">
          {trace.spans.map((span, index) => (
            <article
              id={`span-${span.span_id}`}
              key={span.span_id}
              className="scroll-mt-8 rounded-xl border border-slate-800 bg-[#101522] p-6"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wider text-indigo-400">
                    Span {index + 1} · {span.span_type}
                  </p>

                  <h2 className="mt-2 text-lg font-semibold">
                    {span.name}
                  </h2>
                </div>

                <span
                  className={
                    span.status === "ok"
                      ? "rounded-full bg-emerald-500/10 px-3 py-1 text-sm text-emerald-400"
                      : "rounded-full bg-red-500/10 px-3 py-1 text-sm text-red-400"
                  }
                >
                  ● {span.status}
                </span>
              </div>

              <div className="mt-5 grid gap-4 border-t border-slate-800 pt-5 sm:grid-cols-2">
                <div>
                  <p className="text-xs text-slate-500">
                    Timestamp
                  </p>

                  <p className="mt-1 text-sm">
                    {new Date(
                      span.timestamp
                    ).toLocaleString()}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-slate-500">
                    Span ID
                  </p>

                  <p className="mt-1 break-all font-mono text-xs text-slate-300">
                    {span.span_id}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-slate-500">
                    Parent Span ID
                  </p>

                  <p className="mt-1 break-all font-mono text-xs text-slate-300">
                    {span.parent_span_id ?? "Root span"}
                  </p>
                </div>
              </div>

              <div className="mt-5">
                <p className="mb-2 text-sm font-medium text-slate-300">
                  Metadata
                </p>

                <pre className="overflow-x-auto rounded-lg bg-[#080b12] p-4 text-xs text-slate-300">
                  {JSON.stringify(
                    span.metadata,
                    null,
                    2
                  )}
                </pre>
              </div>
            </article>
          ))}
        </section>
      </div>
    </main>
  );
}
