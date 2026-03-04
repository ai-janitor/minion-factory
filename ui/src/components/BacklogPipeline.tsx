// Backlog Pipeline — funnel/kanban view of pre-requirement items (View 2)
//
// Purpose: Show backlog items flowing through stages (open → promoted → killed/deferred).
// Data source: GET /projects/{name}/backlog
// Shows: items grouped by status, priority color coding, promoted_to link.
// Highlight: items stuck >1hr in "open" get yellow/red treatment.
//
// PSEUDO: useSWR("/projects/{project}/backlog", fetcher, { refreshInterval: 10000 })
// PSEUDO: group items by status: open, promoted, killed, deferred
// PSEUDO: for open items, compute age = now - created_at, color by staleness
// PSEUDO: render kanban columns or grouped list

import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

interface BacklogItem {
  id: number
  file_path: string
  type: string
  title: string
  priority: string
  status: string
  source: string | null
  promoted_to: string | null
  flow_hint: string | null
  created_by: string | null
  created_at: string
  updated_at: string
}

const STATUS_COLUMNS = [
  { status: "open", label: "Open", headerClass: "text-blue-400 border-blue-800" },
  { status: "promoted", label: "Promoted", headerClass: "text-green-400 border-green-800" },
  { status: "deferred", label: "Deferred", headerClass: "text-yellow-400 border-yellow-800" },
  { status: "killed", label: "Killed", headerClass: "text-red-400 border-red-800" },
]

const PRIORITY_BADGE: Record<string, string> = {
  critical: "border-red-700 text-red-400",
  high: "border-orange-700 text-orange-400",
  medium: "border-yellow-700 text-yellow-400",
  low: "border-zinc-600 text-zinc-500",
  unset: "border-zinc-700 text-zinc-600",
}

const TYPE_BADGE: Record<string, string> = {
  idea: "border-purple-700 text-purple-400",
  bug: "border-red-700 text-red-400",
  debt: "border-yellow-700 text-yellow-400",
  request: "border-blue-700 text-blue-400",
}

function ageColor(createdAt: string): string {
  const mins = (Date.now() - new Date(createdAt).getTime()) / 60000
  if (mins < 60) return ""
  if (mins < 180) return "border-l-2 border-l-yellow-700"
  return "border-l-2 border-l-red-700"
}

function ageLabel(createdAt: string): string {
  const mins = Math.round((Date.now() - new Date(createdAt).getTime()) / 60000)
  if (mins < 60) return `${mins}m`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs}h`
  return `${Math.round(hrs / 24)}d`
}

export default function BacklogPipeline() {
  const { data, isLoading, error } = useSWR<{ backlog: BacklogItem[] }>(
    "/projects/minion-factory/backlog",
    fetcher,
    { refreshInterval: 10000 }
  )

  if (isLoading) return <p className="text-[11px] text-zinc-500 font-mono">loading backlog…</p>
  if (error || !data) return <p className="text-[11px] text-red-500 font-mono">failed to load backlog</p>

  const byStatus: Record<string, BacklogItem[]> = {}
  for (const col of STATUS_COLUMNS) byStatus[col.status] = []
  for (const item of data.backlog) {
    if (byStatus[item.status]) byStatus[item.status].push(item)
  }

  return (
    <div className="flex gap-3 overflow-x-auto pb-2 flex-wrap">
      {STATUS_COLUMNS.map(col => (
        <div key={col.status} className="flex flex-col min-w-[220px] flex-1 max-w-[300px]">
          {/* Column header */}
          <div className={`flex items-center justify-between px-2 py-1.5 mb-2 rounded border ${col.headerClass}`}>
            <span className="text-xs font-semibold uppercase tracking-wider">{col.label}</span>
            <span className="text-[10px] font-mono opacity-60">{byStatus[col.status].length}</span>
          </div>

          {/* Items */}
          <div className="flex-1 space-y-2 overflow-y-auto" style={{ maxHeight: "calc(100vh - 240px)" }}>
            {byStatus[col.status].length === 0 && (
              <div className="text-zinc-700 text-xs text-center py-4">—</div>
            )}
            {byStatus[col.status].map(item => (
              <Card
                key={item.id}
                className={`bg-zinc-900 border-zinc-700 ${col.status === "open" ? ageColor(item.created_at) : ""}`}
              >
                <CardContent className="px-3 py-2.5 space-y-1.5">
                  {/* Title + ID */}
                  <div className="flex items-start justify-between gap-1">
                    <span className="text-xs text-white font-medium leading-snug line-clamp-2">{item.title}</span>
                    <span className="text-zinc-600 font-mono text-[10px] shrink-0">#{item.id}</span>
                  </div>

                  {/* Badges row */}
                  <div className="flex flex-wrap gap-1 items-center">
                    <Badge variant="outline" className={`text-[10px] px-1 py-0 ${TYPE_BADGE[item.type] || "border-zinc-600 text-zinc-400"}`}>
                      {item.type}
                    </Badge>
                    {item.priority !== "unset" && (
                      <Badge variant="outline" className={`text-[10px] px-1 py-0 ${PRIORITY_BADGE[item.priority] || PRIORITY_BADGE.unset}`}>
                        {item.priority}
                      </Badge>
                    )}
                    {col.status === "open" && (
                      <span className="text-[10px] font-mono text-zinc-500 ml-auto">{ageLabel(item.created_at)}</span>
                    )}
                  </div>

                  {/* Promoted-to link */}
                  {item.promoted_to && (
                    <p className="text-[10px] text-green-600 font-mono truncate">→ {item.promoted_to}</p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
