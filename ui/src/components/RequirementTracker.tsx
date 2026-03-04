// Requirement Tracker — stage badges + stall detection (View 3)
//
// Purpose: Show all requirements with current DAG stage, time-in-stage, stall color coding.
// Data source: GET /api/tasks (uses compat route which reads from project DB requirements)
//              GET /projects/{name}/requirements (when multi-project is wired)
// Shows: table with stage badges, time-in-stage countdown, completion percentage.
// Color coding: green (progressing), yellow (>30min same stage), red (>1hr same stage).
//
// PSEUDO: useSWR("/projects/{project}/requirements", fetcher, { refreshInterval: 10000 })
// PSEUDO: for each requirement:
//   compute time_in_stage = now - updated_at
//   color = green if < 30min, yellow if 30-60min, red if > 60min
//   show stage badge, completion_pct bar, linked task count
// PSEUDO: click row → fetch /requirements/{id}/lineage → show modal with full history

import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

interface Requirement {
  id: number
  file_path: string
  origin: string
  stage: string
  flow_type: string
  created_at: string
  updated_at: string
  linked_task_count: number
  completion_pct: number
}

const STAGE_COLORS: Record<string, string> = {
  seed: "border-zinc-600 text-zinc-400",
  itemizing: "border-blue-700 text-blue-400",
  itemized: "border-blue-700 text-blue-400",
  investigating: "border-cyan-700 text-cyan-400",
  findings_ready: "border-cyan-700 text-cyan-400",
  decomposing: "border-purple-700 text-purple-400",
  tasked: "border-yellow-700 text-yellow-400",
  in_progress: "border-orange-700 text-orange-400",
  completed: "border-green-700 text-green-400",
}

function staleColor(updatedAt: string): string {
  const mins = (Date.now() - new Date(updatedAt).getTime()) / 60000
  if (mins < 30) return "text-green-400"
  if (mins < 60) return "text-yellow-400"
  return "text-red-400"
}

function timeInStage(updatedAt: string): string {
  const mins = Math.round((Date.now() - new Date(updatedAt).getTime()) / 60000)
  if (mins < 60) return `${mins}m`
  return `${Math.round(mins / 60)}h`
}

function reqName(filePath: string): string {
  const parts = filePath.split("/")
  return parts[parts.length - 1]
}

export default function RequirementTracker() {
  const { data, isLoading, error } = useSWR<{ requirements: Requirement[] }>(
    "/projects/minion-factory/requirements",
    fetcher,
    { refreshInterval: 10000 }
  )

  if (isLoading) return <p className="text-[11px] text-zinc-500 font-mono">loading requirements…</p>
  if (error || !data) return <p className="text-[11px] text-red-500 font-mono">failed to load requirements</p>

  return (
    <Card className="bg-zinc-900 border-zinc-700">
      <CardHeader className="pb-2">
        <CardTitle className="text-xs uppercase tracking-wider text-zinc-500">Requirements</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-1">
          {data.requirements.map(req => (
            <div key={req.id} className="flex items-center gap-3 py-1.5 border-b border-zinc-800 last:border-0">
              <Badge variant="outline" className={`text-[10px] px-1.5 py-0 shrink-0 ${STAGE_COLORS[req.stage] || "border-zinc-600 text-zinc-400"}`}>
                {req.stage}
              </Badge>
              <span className="text-xs font-mono text-zinc-300 truncate flex-1">{reqName(req.file_path)}</span>
              <span className={`text-[10px] font-mono shrink-0 ${staleColor(req.updated_at)}`}>
                {timeInStage(req.updated_at)}
              </span>
              <span className="text-[10px] font-mono text-zinc-500 shrink-0 w-12 text-right">
                {req.completion_pct}%
              </span>
              <span className="text-[10px] font-mono text-zinc-600 shrink-0">
                {req.linked_task_count} tasks
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
