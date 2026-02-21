// Live agent panel — replaces MockAgentPanel with real /api/agents data.
// Liveness derived from last_seen: active <2m, idle 2-10m, dead >10m or null.
import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"

// --------------------------------------------------------------------------
// Types
// --------------------------------------------------------------------------

interface AgentTask {
  id: number
  title: string
  status: string
}

interface Agent {
  name: string
  agent_class: string
  model: string
  status: string
  last_seen: string | null
  hp_pct: number | null
  hp_status: "Healthy" | "Wounded" | "CRITICAL" | null
  current_task: AgentTask | null
}

// --------------------------------------------------------------------------
// Helpers
// --------------------------------------------------------------------------

// Returns seconds since last_seen, or Infinity if unknown
function secondsSince(last_seen: string | null): number {
  if (!last_seen) return Infinity
  return (Date.now() - new Date(last_seen).getTime()) / 1000
}

// Relative time label for last_seen
function relativeTime(last_seen: string | null): string {
  if (!last_seen) return "never"
  const secs = secondsSince(last_seen)
  // secondsSince returns NaN when DB emits truthy-but-unparseable strings (e.g. "null")
  if (!isFinite(secs)) return "-"
  if (secs < 60) return `${Math.round(secs)}s ago`
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`
  return `${Math.round(secs / 3600)}h ago`
}

type Liveness = "active" | "idle" | "dead"

function liveness(last_seen: string | null): Liveness {
  const secs = secondsSince(last_seen)
  if (secs < 120) return "active"
  if (secs < 600) return "idle"
  return "dead"
}

// --------------------------------------------------------------------------
// Style maps
// --------------------------------------------------------------------------

const HP_BAR_COLOR: Record<string, string> = {
  Healthy:  "bg-green-500",
  Wounded:  "bg-yellow-500",
  CRITICAL: "bg-red-500",
}

const CLASS_COLOR: Record<string, string> = {
  lead:    "text-purple-400 border-purple-700",
  coder:   "text-blue-400 border-blue-700",
  builder: "text-orange-400 border-orange-700",
  recon:   "text-cyan-400 border-cyan-700",
  oracle:  "text-emerald-400 border-emerald-700",
}

const LIVENESS_DOT: Record<Liveness, string> = {
  active: "bg-green-500",
  idle:   "bg-yellow-500",
  dead:   "bg-red-600",
}

const LIVENESS_TITLE: Record<Liveness, string> = {
  active: "active",
  idle:   "idle",
  dead:   "dead / unreachable",
}

// --------------------------------------------------------------------------
// Component
// --------------------------------------------------------------------------

export default function AgentPanel() {
  const { data, isLoading, error } = useSWR<Agent[]>("/api/agents", fetcher, {
    refreshInterval: 5000,
  })

  if (isLoading) {
    return <p className="text-[11px] text-zinc-500 font-mono">loading agents…</p>
  }

  if (error || !data) {
    return <p className="text-[11px] text-red-500 font-mono">failed to load agents</p>
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
      {data.map(agent => {
        const live = liveness(agent.last_seen)
        const hpColor = agent.hp_status ? HP_BAR_COLOR[agent.hp_status] : "bg-zinc-600"
        const hpPct = agent.hp_pct ?? 0

        return (
          <Card key={agent.name} className="bg-zinc-900 border-zinc-700">
            <CardContent className="px-3 py-3 space-y-2">

              {/* Name + liveness dot + class badge */}
              <div className="flex items-center justify-between gap-1">
                <div className="flex items-center gap-1.5 min-w-0">
                  {/* Liveness indicator */}
                  <span
                    className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${LIVENESS_DOT[live]}`}
                    title={LIVENESS_TITLE[live]}
                  />
                  <span className="text-sm font-mono font-semibold text-white truncate">
                    {live === "dead" ? "💀 " : ""}{agent.name}
                  </span>
                </div>
                <Badge
                  variant="outline"
                  className={`text-[10px] px-1 py-0 shrink-0 ${CLASS_COLOR[agent.agent_class] ?? "text-zinc-400 border-zinc-600"}`}
                >
                  {agent.agent_class}
                </Badge>
              </div>

              {/* HP bar */}
              <div className="space-y-0.5">
                <div className="flex justify-between text-[10px] text-zinc-400">
                  <span>HP</span>
                  {agent.hp_pct !== null ? (
                    <span className={agent.hp_status === "CRITICAL" ? "text-red-400 font-bold" : ""}>
                      {agent.hp_pct}%
                    </span>
                  ) : (
                    <span className="text-zinc-600">—</span>
                  )}
                </div>
                <div className="bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${hpColor}`}
                    style={{ width: `${hpPct}%` }}
                  />
                </div>
              </div>

              {/* Status */}
              <p className="text-[10px] text-zinc-400 truncate">{agent.status}</p>

              {/* Current task */}
              {agent.current_task && (
                <p className="text-[10px] text-zinc-500 italic truncate">
                  ↳ {agent.current_task.title}
                </p>
              )}

              {/* Model + last_seen */}
              <div className="flex justify-between text-[10px] text-zinc-600 font-mono">
                <span className="truncate">{agent.model}</span>
                <span className="shrink-0 ml-1">{relativeTime(agent.last_seen)}</span>
              </div>

            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
