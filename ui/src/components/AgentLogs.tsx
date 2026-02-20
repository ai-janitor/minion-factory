import { useState } from "react"
import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

interface AgentLog {
  agent: string
  lines: string[]
}

export default function AgentLogs() {
  const [selected, setSelected] = useState<string | null>(null)
  const { data: allLogs } = useSWR<Record<string, string>>(
    "/api/logs",
    fetcher,
    { refreshInterval: 5000 }
  )
  const { data: detail } = useSWR<AgentLog>(
    selected ? `/api/logs/${selected}?tail=200` : null,
    fetcher,
    { refreshInterval: 3000 }
  )

  const agents = allLogs ? Object.keys(allLogs).sort() : []

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {agents.map(name => (
          <Badge
            key={name}
            variant={selected === name ? "default" : "outline"}
            className="cursor-pointer"
            onClick={() => setSelected(selected === name ? null : name)}
          >
            {name}
          </Badge>
        ))}
      </div>

      {selected && detail && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-mono">{selected}.log</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-xs font-mono bg-black text-green-400 p-3 rounded-md max-h-[500px] overflow-y-auto whitespace-pre-wrap break-all">
              {detail.lines.join("\n") || "(empty)"}
            </pre>
          </CardContent>
        </Card>
      )}

      {!selected && agents.length > 0 && (
        <div className="text-sm text-muted-foreground">
          Click an agent name to view their terminal log.
        </div>
      )}
    </div>
  )
}
