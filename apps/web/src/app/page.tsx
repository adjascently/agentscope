
import Link from "next/link";

type AgentRun = {
  run_id: string;
  span_count: number;
  started_at: string;
  last_event_at: string;
  error_count: number;
  status: "ok" | "error";
};

type RunsResponse = {
  count: number;
  runs: AgentRun[];
};

async function getRuns(): Promise<RunsResponse> {
  const response = await fetch("http://127.0.0.1:8000/v1/runs", {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Failed to fetch agent runs");
  }

  return response.json();
}
export const instant = false;
export default async function Home() {
  let data: RunsResponse = { count: 0, runs: [] };
  let error = false;

  try {
    data = await getRuns();
  } catch {
    error = true;
  }

  return (
    <main className="min-h-screen bg-[#080b12] text-white">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <header className="mb-12 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              AgentScope
            </h1>
            <p className="mt-2 text-sm text-slate-400">
              AI Agent Observability Platform
            </p>
          </div>

          <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-xs text-emerald-400">
            ● System Online
          </span>
        </header>

        <section className="mb-10 grid gap-4 md:grid-cols-3">
          <MetricCard
            title="Total Runs"
            value={data.count.toString()}
          />
          <MetricCard
            title="Total Spans"
            value={data.runs
              .reduce((sum, run) => sum + run.span_count, 0)
              .toString()}
          />
          <MetricCard
            title="Failed Runs"
            value={data.runs
              .filter((run) => run.status === "error")
              .length.toString()}
          />
        </section>

        <section className="overflow-hidden rounded-xl border border-slate-800 bg-[#101522]">
          <div className="border-b border-slate-800 px-6 py-5">
            <h2 className="text-lg font-semibold">
              Recent Agent Runs
            </h2>
            <p className="mt-1 text-sm text-slate-400">
              Explore execution traces and agent activity
            </p>
          </div>

          {error ? (
            <div className="p-8 text-red-400">
              Unable to connect to AgentScope API.
              Make sure FastAPI is running on port 8000.
            </div>
          ) : data.runs.length === 0 ? (
            <div className="p-8 text-slate-400">
              No agent runs found yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-900/60 text-slate-400">
                  <tr>
                    <th className="px-6 py-4">Run ID</th>
                    <th className="px-6 py-4">Status</th>
                    <th className="px-6 py-4">Spans</th>
                    <th className="px-6 py-4">Errors</th>
                    <th className="px-6 py-4">Started</th>
                  </tr>
                </thead>

                <tbody>
                  {data.runs.map((run) => (
                    <tr
                      key={run.run_id}
                      className="border-t border-slate-800 hover:bg-slate-800/40"
                    >
                      <td className="px-6 py-4 font-mono text-indigo-400">
                        <Link href={`/runs/${run.run_id}`}>
                          {run.run_id.slice(0, 8)}...
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

                      <td className="px-6 py-4 text-slate-400">
                        {new Date(
                          run.started_at
                        ).toLocaleString("en-US", {
                          timeZone: "UTC",
                        })}{" "}
                        UTC
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
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
}: {
  title: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-[#101522] p-6">
      <p className="text-sm text-slate-400">{title}</p>
      <p className="mt-3 text-3xl font-bold">{value}</p>
    </div>
  );
}
