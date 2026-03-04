// Cross-Project Agent Map — HP bars + presence status (View 4)
//
// Purpose: Show all agents across all projects from the network coordinator.
// Data source: GET /who (enhanced with presence, availability, fqn, current_task)
// Shows: agent cards with name, class, project, HP bar, current task, presence dot.
// Sort: HP ascending (critical first), then by project.
//
// PSEUDO: useSWR("/who", fetcher, { refreshInterval: 5000 })
// PSEUDO: sort agents: critical first, then wounded, then healthy
// PSEUDO: render grid of agent cards with:
//   - presence dot (online=green, stale=yellow, offline=red)
//   - name + fqn
//   - class badge
//   - project name
//   - availability badge (idle/busy/blocked/critical)
//   - current task if any

import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

interface NetworkAgent {
  name: string
  agent_class: string
  machine_id: string
  project_path: string
  fqn: string
  presence: "online" | "stale" | "offline"
  availability: "idle" | "busy" | "blocked" | "critical"
  project_name: string | null
  current_task: { id: number; title: string; status: string } | null
  last_seen: string | null
  model: string | null
}

const PRESENCE_DOT: Record<string, string> = {
  online: "bg-green-500",
  stale: "bg-yellow-500",
  offline: "bg-red-600",
}

const AVAIL_COLOR: Record<string, string> = {
  idle: "border-green-700 text-green-400",
  busy: "border-blue-700 text-blue-400",
  blocked: "border-red-700 text-red-400",
  critical: "border-red-700 text-red-400 font-bold",
}

const CLASS_COLOR: Record<string, string> = {
  lead: "text-purple-400 border-purple-700",
  coder: "text-blue-400 border-blue-700",
  builder: "text-orange-400 border-orange-700",
  recon: "text-cyan-400 border-cyan-700",
  oracle: "text-emerald-400 border-emerald-700",
  auditor: "text-yellow-400 border-yellow-700",
}

export default function CrossProjectAgentMap() {
  const { data, isLoading, error } = useSWR<{ agents: NetworkAgent[] }>("/who", fetcher, {
    refreshInterval: 5000,
  })

  if (isLoading) return <p className="text-[11px] text-zinc-500 font-mono">loading agents…</p>
  if (error || !data) return <p className="text-[11px] text-red-500 font-mono">failed to load agents</p>

  // Sort: offline last, critical/blocked first among online
  const sorted = [...data.agents].sort((a, b) => {
    const presOrder = { online: 0, stale: 1, offline: 2 }
    const availOrder = { critical: 0, blocked: 1, busy: 2, idle: 3 }
    const pa = presOrder[a.presence] ?? 2
    const pb = presOrder[b.presence] ?? 2
    if (pa !== pb) return pa - pb
    return (availOrder[a.availability] ?? 3) - (availOrder[b.availability] ?? 3)
  })

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
      {sorted.map(agent => (
        <Card key={agent.fqn} className="bg-zinc-900 border-zinc-700">
          <CardContent className="px-3 py-3 space-y-2">
            {/* Name + presence dot + class badge */}
            <div className="flex items-center justify-between gap-1">
              <div className="flex items-center gap-1.5 min-w-0">
                <span className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${PRESENCE_DOT[agent.presence] || "bg-zinc-600"}`} />
                <span className="text-sm font-mono font-semibold text-white truncate">{agent.name}</span>
              </div>
              <Badge variant="outline" className={`text-[10px] px-1 py-0 shrink-0 ${CLASS_COLOR[agent.agent_class] || "text-zinc-400 border-zinc-600"}`}>
                {agent.agent_class}
              </Badge>
            </div>

            {/* Project + availability */}
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-zinc-500 font-mono truncate">{agent.project_name || "—"}</span>
              <Badge variant="outline" className={`text-[10px] px-1 py-0 ${AVAIL_COLOR[agent.availability] || "border-zinc-600 text-zinc-400"}`}>
                {agent.availability}
              </Badge>
            </div>

            {/* Current task */}
            {agent.current_task && (
              <p className="text-[10px] text-zinc-500 italic truncate">
                ↳ {agent.current_task.title}
              </p>
            )}

            {/* FQN */}
            <p className="text-[10px] text-zinc-600 font-mono truncate">{agent.fqn}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
