
import Link from "next/link";

export const instant = false;

type RunStatus = "ok" | "error";
type StatusFilter = "all" | RunStatus;

type AgentRun = {
  run_id: string;
  span_count: number;
  started_at: string;
  last_event_at: string;
  error_count: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  status: RunStatus;
};

type RunsResponse = {
  count: number;
  runs: AgentRun[];
};

type HomeProps = {
  searchParams: Promise<{
    status?: string | string[];
  }>;
};

async function getRuns(
  status: StatusFilter
): Promise<RunsResponse> {
  const apiBaseUrl =
  process.env.AGENTSCOPE_API_URL ??
  "http://127.0.0.1:8000";

const url = new URL(
  "/v1/runs",
  apiBaseUrl
);

  url.searchParams.set("limit", "100");

  if (status !== "all") {
    url.searchParams.set("status", status);
  }

  const response = await fetch(url.toString(), {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(
      `AgentScope API returned ${response.status}`
    );
  }

  return response.json();
}

function formatCost(cost: number): string {
  if (cost === 0) return "$0.00000";
  if (cost < 0.00001) return "<$0.00001";
  return `$${cost.toFixed(5)}`;
}

function formatDate(date: string): string {
  return (
    new Date(date).toLocaleString("en-US", {
      timeZone: "UTC",
    }) + " UTC"
  );
}

export default async function Home({
  searchParams,
}: HomeProps) {
  const params = await searchParams;
  const requestedStatus = Array.isArray(params.status)
    ? params.status[0]
    : params.status;

  const status: StatusFilter =
    requestedStatus === "ok" ||
    requestedStatus === "error"
      ? requestedStatus
      : "all";

  let data: RunsResponse = {
    count: 0,
    runs: [],
  };

  let error = false;

  try {
    data = await getRuns(status);
  } catch (err) {
    console.error("Failed to fetch runs:", err);
    error = true;
  }

  const totalSpans = data.runs.reduce(
    (sum, run) => sum + run.span_count,
    0
  );

  const failedRuns = data.runs.filter(
    (run) => run.status === "error"
  ).length;

  const totalInputTokens = data.runs.reduce(
    (sum, run) => sum + run.input_tokens,
    0
  );

  const totalOutputTokens = data.runs.reduce(
    (sum, run) => sum + run.output_tokens,
    0
  );

  const totalTokens =
    totalInputTokens + totalOutputTokens;

  const totalCost = data.runs.reduce(
    (sum, run) =>
      sum + Number(run.estimated_cost_usd),
    0
  );

  const filters: {
    label: string;
    value: StatusFilter;
    href: string;
  }[] = [
    {
      label: "All Runs",
      value: "all",
      href: "/",
    },
    {
      label: "Successful",
      value: "ok",
      href: "/?status=ok",
    },
    {
      label: "Failed",
      value: "error",
      href: "/?status=error",
    },
  ];

  return (
    <main className="min-h-screen bg-[#080b12] text-white">
      <div className="mx-auto max-w-7xl px-6 py-12">
        <header className="mb-12 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              AgentScope
            </h1>

            <p className="mt-2 text-sm text-slate-400">
              AI Agent Observability Platform
            </p>
          </div>

          <span
            className={`rounded-full border px-4 py-2 text-xs ${
              error
                ? "border-red-500/30 bg-red-500/10 text-red-400"
                : "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
            }`}
          >
            {error
              ? "● API Unavailable"
              : "● API Connected"}
          </span>
        </header>

        <section className="mb-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <MetricCard
            title="Runs"
            value={data.count.toLocaleString()}
          />

          <MetricCard
            title="Total Spans"
            value={totalSpans.toLocaleString()}
          />

          <MetricCard
            title="Failed Runs"
            value={failedRuns.toLocaleString()}
            accent="red"
          />

          <MetricCard
            title="Total Tokens"
            value={totalTokens.toLocaleString()}
            subtitle={`${totalInputTokens.toLocaleString()} input · ${totalOutputTokens.toLocaleString()} output`}
          />

          <MetricCard
            title="Estimated LLM Cost"
            value={formatCost(totalCost)}
            accent="indigo"
          />
        </section>

        <section className="overflow-hidden rounded-xl border border-slate-800 bg-[#101522]">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 px-6 py-5">
            <div>
              <h2 className="text-lg font-semibold">
                Recent Agent Runs
              </h2>

              <p className="mt-1 text-sm text-slate-400">
                Explore execution traces, token usage,
                and agent activity
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              {filters.map((filter) => {
                const active =
                  status === filter.value;

                return (
                  <Link
                    key={filter.value}
                    href={filter.href}
                    className={`rounded-lg border px-4 py-2 text-sm transition-colors ${
                      active
                        ? "border-indigo-500 bg-indigo-500/20 text-indigo-300"
                        : "border-slate-700 text-slate-400 hover:border-slate-500 hover:text-white"
                    }`}
                  >
                    {filter.label}
                  </Link>
                );
              })}
            </div>
          </div>

          {error ? (
            <div className="p-8 text-red-400">
              Unable to connect to AgentScope API.
              Make sure FastAPI is running on port
              8000 and PostgreSQL is available.
            </div>
          ) : data.runs.length === 0 ? (
            <div className="p-8 text-slate-400">
              No runs found for this filter.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-900/60 text-slate-400">
                  <tr>
                    <th className="px-6 py-4">
                      Run ID
                    </th>
                    <th className="px-6 py-4">
                      Status
                    </th>
                    <th className="px-6 py-4">
                      Spans
                    </th>
                    <th className="px-6 py-4">
                      Errors
                    </th>
                    <th className="px-6 py-4">
                      Tokens
                    </th>
                    <th className="px-6 py-4">
                      Est. Cost
                    </th>
                    <th className="px-6 py-4">
                      Started
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {data.runs.map((run) => {
                    const runTokens =
                      run.input_tokens +
                      run.output_tokens;

                    return (
                      <tr
                        key={run.run_id}
                        className="border-t border-slate-800 transition-colors hover:bg-slate-800/40"
                      >
                        <td className="px-6 py-4 font-mono text-indigo-400">
                          <Link
                            href={`/runs/${run.run_id}`}
                            className="hover:text-indigo-300 hover:underline"
                            title={run.run_id}
                          >
                            {run.run_id.slice(0, 8)}
                            ...
                          </Link>
                        </td>

                        <td className="px-6 py-4">
                          <span
                            className={
                              run.status === "ok"
                                ? "text-emerald-400"
                                : "text-red-400"
                            }
                          >
                            ● {run.status}
                          </span>
                        </td>

                        <td className="px-6 py-4">
                          {run.span_count}
                        </td>

                        <td className="px-6 py-4">
                          {run.error_count}
                        </td>

                        <td className="px-6 py-4">
                          {runTokens.toLocaleString()}
                        </td>

                        <td className="px-6 py-4 text-slate-300">
                          {formatCost(
                            Number(
                              run.estimated_cost_usd
                            )
                          )}
                        </td>

                        <td className="whitespace-nowrap px-6 py-4 text-slate-400">
                          {formatDate(run.started_at)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {!error && (
            <div className="border-t border-slate-800 px-6 py-4 text-xs text-slate-500">
              Showing {data.runs.length}{" "}
              {status === "all"
                ? "recent runs"
                : status === "ok"
                  ? "successful runs"
                  : "failed runs"}
              . Token usage and estimated costs
              reflect available trace metadata.
              Demo pricing is simulated.
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function MetricCard({
  title,
  value,
  subtitle,
  accent = "default",
}: {
  title: string;
  value: string;
  subtitle?: string;
  accent?: "default" | "red" | "indigo";
}) {
  const valueColor =
    accent === "red"
      ? "text-red-400"
      : accent === "indigo"
        ? "text-indigo-300"
        : "text-white";

  return (
    <div className="rounded-xl border border-slate-800 bg-[#101522] p-6">
      <p className="text-sm text-slate-400">
        {title}
      </p>

      <p
        className={`mt-3 text-2xl font-bold tracking-tight ${valueColor}`}
      >
        {value}
      </p>

      {subtitle && (
        <p className="mt-2 text-xs text-slate-500">
          {subtitle}
        </p>
      )}
    </div>
  );
}
