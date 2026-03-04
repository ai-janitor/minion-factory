// Alert Panel — severity-sorted persistent alerts (View 6)
//
// Purpose: Show actionable alerts for sys-lead monitoring.
// Data source: GET /alerts
// Shows: severity-sorted list (critical → warning). Types: stalled_requirement,
//        hp_critical, unread_messages. Persistent until resolved.
//
// PSEUDO: useSWR("/alerts", fetcher, { refreshInterval: 5000 })
// PSEUDO: render list of alert cards sorted by severity
// PSEUDO: critical = red border, warning = yellow border
// PSEUDO: each alert shows type icon, description, project, agent/req info

import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

interface Alert {
  type: string
  severity: "critical" | "warning" | "info"
  project: string
  agent?: string
  requirement_id?: number
  file_path?: string
  stage?: string
  stalled_minutes?: number
  hp_pct?: number
  count?: number
  oldest_minutes?: number
}

const SEVERITY_STYLE: Record<string, string> = {
  critical: "border-red-700 bg-red-950/30",
  warning: "border-yellow-700 bg-yellow-950/20",
  info: "border-zinc-700 bg-zinc-900",
}

const SEVERITY_BADGE: Record<string, string> = {
  critical: "border-red-700 text-red-400",
  warning: "border-yellow-700 text-yellow-400",
  info: "border-zinc-600 text-zinc-400",
}

function alertDescription(alert: Alert): string {
  switch (alert.type) {
    case "stalled_requirement":
      return `Req #${alert.requirement_id} stuck in "${alert.stage}" for ${alert.stalled_minutes}m`
    case "hp_critical":
      return `${alert.agent} HP at ${alert.hp_pct}%`
    case "unread_messages":
      return `${alert.agent} has ${alert.count} unread msg(s), oldest ${alert.oldest_minutes}m ago`
    default:
      return alert.type
  }
}

export default function AlertPanel() {
  const { data, isLoading, error } = useSWR<{ alerts: Alert[] }>("/alerts", fetcher, {
    refreshInterval: 5000,
  })

  if (isLoading) return <p className="text-[11px] text-zinc-500 font-mono">loading alerts…</p>
  if (error || !data) return <p className="text-[11px] text-red-500 font-mono">failed to load alerts</p>

  if (data.alerts.length === 0) {
    return (
      <Card className="bg-zinc-900 border-zinc-700">
        <CardContent className="py-6 text-center">
          <p className="text-sm text-zinc-500 font-mono">No active alerts</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-2">
      {data.alerts.map((alert, i) => (
        <Card key={i} className={`${SEVERITY_STYLE[alert.severity] || SEVERITY_STYLE.info}`}>
          <CardContent className="px-4 py-3 flex items-center gap-3">
            <Badge variant="outline" className={`text-[10px] px-1.5 py-0 shrink-0 uppercase ${SEVERITY_BADGE[alert.severity] || SEVERITY_BADGE.info}`}>
              {alert.severity}
            </Badge>
            <span className="text-xs font-mono text-zinc-300 flex-1">{alertDescription(alert)}</span>
            <span className="text-[10px] font-mono text-zinc-500 shrink-0">{alert.project}</span>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
