// Mock message feed for scaffold — hardcoded chat-style messages
// Real version will swap MOCK_MESSAGES for useSWR("/api/messages")
import { Badge } from "@/components/ui/badge"

interface MockMessage {
  id: number
  from: string
  to: string
  content: string
  timestamp: string
  is_cc: boolean
}

const MOCK_MESSAGES: MockMessage[] = [
  {
    id: 1,
    from: "splinter",
    to: "leo",
    content: "SCOPE CHANGE: We need a SCAFFOLD, not a full working website. Priority: T1 bugfix first, then minimal layout shell with mocked data. Tasks #3-#7 are ON HOLD.",
    timestamp: "13:10:20",
    is_cc: false,
  },
  {
    id: 2,
    from: "april",
    to: "leo",
    content: "TS6133 fix for KanbanColumn (TaskBoard.tsx:105): prefix status with underscore — `_status: string` — tells TS it's intentionally unused. Least-invasive option.",
    timestamp: "13:10:05",
    is_cc: false,
  },
  {
    id: 3,
    from: "splinter",
    to: "commander",
    content: "SITREP: raph caught T1 kanban build fail (TS6133 unused param). Reassigned to leo for one-liner fix. mikey and april both at 0% HP — need respawn if more recon work needed.",
    timestamp: "13:09:38",
    is_cc: false,
  },
  {
    id: 4,
    from: "raph",
    to: "splinter",
    content: "Copy on T1 reassignment to leo. Holding build context — ready to re-verify after leo patches. Standing by.",
    timestamp: "13:09:43",
    is_cc: false,
  },
  {
    id: 5,
    from: "commander",
    to: "splinter",
    content: "Scope correction: top priority is a SCAFFOLD, not a full working website. Build a minimal example UI so we can see the layout and give feedback. No real functionality needed yet — just the structure.",
    timestamp: "13:09:48",
    is_cc: false,
  },
  {
    id: 6,
    from: "leo",
    to: "splinter",
    content: "T2 server endpoints shipped. /api/messages, /api/flows/:type, /api/agents+current_task all live and tested. Ready for scaffold work.",
    timestamp: "13:12:00",
    is_cc: false,
  },
]

const AGENT_COLOR: Record<string, string> = {
  splinter:  "text-purple-400",
  leo:       "text-blue-400",
  raph:      "text-red-400",
  mikey:     "text-orange-400",
  april:     "text-green-400",
  commander: "text-yellow-400",
}

function agentColor(name: string): string {
  return AGENT_COLOR[name] ?? "text-zinc-300"
}

export default function MockMessageFeed() {
  return (
    <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
      {MOCK_MESSAGES.map(msg => (
        <div key={msg.id} className="rounded-lg bg-zinc-900 border border-zinc-800 px-3 py-2 space-y-1">
          {/* Header row */}
          <div className="flex items-center gap-2 text-[11px]">
            <span className={`font-mono font-semibold ${agentColor(msg.from)}`}>{msg.from}</span>
            <span className="text-zinc-600">→</span>
            <span className={`font-mono ${agentColor(msg.to)}`}>{msg.to}</span>
            {msg.is_cc && (
              <Badge variant="outline" className="text-[9px] px-1 py-0 text-zinc-500 border-zinc-700">CC</Badge>
            )}
            <span className="ml-auto text-zinc-600 font-mono">{msg.timestamp}</span>
          </div>

          {/* Content */}
          <p className="text-xs text-zinc-300 leading-relaxed">{msg.content}</p>
        </div>
      ))}
    </div>
  )
}
