// Live message feed — replaces MockMessageFeed with real /api/messages data.
// Chat-style bubbles, auto-refresh 3s via SWR, auto-scroll to latest.
import { useEffect, useRef } from "react"
import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import { Badge } from "@/components/ui/badge"

// --------------------------------------------------------------------------
// Types
// --------------------------------------------------------------------------

interface Message {
  id: number
  from_agent: string
  to_agent: string
  content: string
  timestamp: string
  read_flag: number
  is_cc: number
}

// --------------------------------------------------------------------------
// Agent class color mapping (lead=gold, coder=blue, oracle=purple,
// builder=green, recon=orange). Falls back to zinc for unknown agents.
// --------------------------------------------------------------------------

// Maps agent name → class. Populated from /api/agents if available,
// but we derive color from known class names embedded in agent names as a heuristic.
// Primary source: /api/agents endpoint which includes agent_class field.
interface AgentInfo {
  name: string
  agent_class: string
}

const CLASS_COLOR: Record<string, string> = {
  lead:    "text-yellow-400",
  coder:   "text-blue-400",
  oracle:  "text-purple-400",
  builder: "text-green-400",
  recon:   "text-orange-400",
  planner: "text-cyan-400",
  auditor: "text-pink-400",
}

function useAgentClassMap(): Record<string, string> {
  const { data: agents } = useSWR<AgentInfo[]>("/api/agents", fetcher, {
    refreshInterval: 30_000,
  })
  if (!agents) return {}
  return Object.fromEntries(agents.map(a => [a.name, a.agent_class]))
}

function agentColor(name: string, classMap: Record<string, string>): string {
  const cls = classMap[name]
  return CLASS_COLOR[cls] ?? "text-zinc-300"
}

// Format ISO timestamp → HH:MM:SS, or pass through if already short
function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    })
  } catch {
    return ts
  }
}

// --------------------------------------------------------------------------
// Component
// --------------------------------------------------------------------------

export default function MessageFeed() {
  const bottomRef = useRef<HTMLDivElement>(null)

  // API returns newest-first; we reverse for chat order (oldest at top)
  const { data: rawMessages, isLoading } = useSWR<Message[]>(
    "/api/messages",
    fetcher,
    { refreshInterval: 3000 }
  )
  const messages = rawMessages ? [...rawMessages].reverse() : []

  const classMap = useAgentClassMap()

  // Auto-scroll to bottom whenever messages update
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages.length])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32 text-zinc-500 text-xs">
        Loading messages…
      </div>
    )
  }

  if (!messages.length) {
    return (
      <div className="flex items-center justify-center h-32 text-zinc-500 text-xs">
        No messages yet
      </div>
    )
  }

  return (
    <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
      {messages.map(msg => (
        <div
          key={msg.id}
          className="rounded-lg bg-zinc-900 border border-zinc-800 px-3 py-2 space-y-1"
        >
          {/* Header row: from → to, CC badge, timestamp */}
          <div className="flex items-center gap-2 text-[11px]">
            <span className={`font-mono font-semibold ${agentColor(msg.from_agent, classMap)}`}>
              {msg.from_agent}
            </span>
            <span className="text-zinc-600">→</span>
            <span className={`font-mono ${agentColor(msg.to_agent, classMap)}`}>
              {msg.to_agent}
            </span>
            {msg.is_cc === 1 && (
              <Badge
                variant="outline"
                className="text-[9px] px-1 py-0 text-zinc-500 border-zinc-700"
              >
                CC
              </Badge>
            )}
            <span className="ml-auto text-zinc-600 font-mono">
              {formatTime(msg.timestamp)}
            </span>
          </div>

          {/* Message content */}
          <p className="text-xs text-zinc-300 leading-relaxed">{msg.content}</p>
        </div>
      ))}

      {/* Scroll anchor */}
      <div ref={bottomRef} />
    </div>
  )
}
