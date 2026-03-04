// System Overview — cross-project aggregation dashboard (View 1)
//
// Purpose: Show sys-lead a single command-center screen with counts across all projects.
// Data source: GET /overview
// Shows: project count, backlog by status, requirements by stage, tasks by status,
//        agents by HP tier (healthy/wounded/critical).
// Organization: Summary cards in a grid layout. Each card shows a category with counts.
//
// PSEUDO: useSWR("/overview", fetcher, { refreshInterval: 10000 })
// PSEUDO: render grid of stat cards:
//   - Project count
//   - Requirements by stage (seed, itemized, in_progress, completed, ...)
//   - Tasks by status (open, assigned, in_progress, qe, closed, ...)
//   - Agents by HP tier (healthy, wounded, critical, unknown)
// PSEUDO: each card shows label + count + optional bar/badge

import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

interface OverviewData {
  project_count: number
  projects: string[]
  requirements: Record<string, number>
  tasks: Record<string, number>
  agents: {
    total: number
    by_class: Record<string, number>
    by_hp_tier: { healthy: number; wounded: number; critical: number; unknown: number }
  }
}

export default function SystemOverview() {
  const { data, isLoading, error } = useSWR<OverviewData>("/overview", fetcher, {
    refreshInterval: 10000,
  })

  if (isLoading) return <p className="text-[11px] text-zinc-500 font-mono">loading overview…</p>
  if (error || !data) return <p className="text-[11px] text-red-500 font-mono">failed to load overview</p>

  return (
    <div className="space-y-4">
      {/* Project count */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard title="Projects" value={data.project_count} />
        <StatCard title="Agents" value={data.agents.total} />
        <StatCard
          title="Critical"
          value={data.agents.by_hp_tier.critical}
          color={data.agents.by_hp_tier.critical > 0 ? "text-red-400" : "text-zinc-400"}
        />
        <StatCard title="Tasks Open" value={(data.tasks.open || 0) + (data.tasks.assigned || 0) + (data.tasks.in_progress || 0)} />
      </div>

      {/* Requirements by stage */}
      <Card className="bg-zinc-900 border-zinc-700">
        <CardHeader className="pb-2">
          <CardTitle className="text-xs uppercase tracking-wider text-zinc-500">Requirements by Stage</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {Object.entries(data.requirements).map(([stage, count]) => (
              <Badge key={stage} variant="outline" className="text-[11px] font-mono text-zinc-300 border-zinc-600">
                {stage}: {count}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Tasks by status */}
      <Card className="bg-zinc-900 border-zinc-700">
        <CardHeader className="pb-2">
          <CardTitle className="text-xs uppercase tracking-wider text-zinc-500">Tasks by Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {Object.entries(data.tasks).map(([status, count]) => (
              <Badge key={status} variant="outline" className="text-[11px] font-mono text-zinc-300 border-zinc-600">
                {status}: {count}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Agents by class */}
      <Card className="bg-zinc-900 border-zinc-700">
        <CardHeader className="pb-2">
          <CardTitle className="text-xs uppercase tracking-wider text-zinc-500">Agents by Class</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {Object.entries(data.agents.by_class).map(([cls, count]) => (
              <Badge key={cls} variant="outline" className="text-[11px] font-mono text-zinc-300 border-zinc-600">
                {cls}: {count}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function StatCard({ title, value, color }: { title: string; value: number; color?: string }) {
  return (
    <Card className="bg-zinc-900 border-zinc-700">
      <CardContent className="px-4 py-3">
        <p className="text-[10px] text-zinc-500 uppercase tracking-wider">{title}</p>
        <p className={`text-2xl font-bold font-mono ${color || "text-white"}`}>{value}</p>
      </CardContent>
    </Card>
  )
}
