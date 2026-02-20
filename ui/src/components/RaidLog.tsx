import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import { Badge } from "@/components/ui/badge"

interface RaidEntry {
  id: number
  agent_name: string
  entry_file: string
  priority: string
  content: string
  created_at: string
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export default function RaidLog() {
  const { data: entries } = useSWR<RaidEntry[]>("/api/raid-log", fetcher, { refreshInterval: 3000 })

  if (!entries) return <div className="text-muted-foreground p-4">Loading raid log...</div>

  return (
    <div className="max-h-96 overflow-y-auto space-y-2">
      {entries.length === 0 && (
        <div className="text-muted-foreground text-sm p-2">No raid log entries.</div>
      )}
      {entries.map(entry => (
        <div key={entry.id} className="border rounded-lg p-3 text-sm space-y-1">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="font-medium">{entry.agent_name}</span>
              <Badge variant={entry.priority === "high" ? "destructive" : "secondary"} className="text-xs">
                {entry.priority}
              </Badge>
            </div>
            <span className="text-xs text-muted-foreground">{relativeTime(entry.created_at)}</span>
          </div>
          <div className="text-xs text-muted-foreground whitespace-pre-wrap line-clamp-4">
            {entry.content}
          </div>
        </div>
      ))}
    </div>
  )
}
