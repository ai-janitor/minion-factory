// Mock agent panel for scaffold — hardcoded data so commander can evaluate layout
// Real version will swap MOCK_AGENTS for useSWR("/api/agents")
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"

interface MockAgent {
  name: string
  agent_class: string
  model: string
  status: string
  hp_pct: number
  hp_status: "Healthy" | "Wounded" | "CRITICAL"
  current_task: string | null
}

const MOCK_AGENTS: MockAgent[] = [
  {
    name: "splinter",
    agent_class: "lead",
    model: "claude-opus-4-6",
    status: "assigning tasks",
    hp_pct: 72,
    hp_status: "Healthy",
    current_task: null,
  },
  {
    name: "leo",
    agent_class: "coder",
    model: "claude-sonnet-4-6",
    status: "coding scaffold",
    hp_pct: 58,
    hp_status: "Healthy",
    current_task: "T7: UI Scaffold",
  },
  {
    name: "raph",
    agent_class: "builder",
    model: "claude-sonnet-4-6",
    status: "standing by",
    hp_pct: 31,
    hp_status: "Wounded",
    current_task: null,
  },
  {
    name: "mikey",
    agent_class: "recon",
    model: "claude-haiku-4-5",
    status: "0% HP — exhausted",
    hp_pct: 0,
    hp_status: "CRITICAL",
    current_task: null,
  },
]

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
}

export default function MockAgentPanel() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {MOCK_AGENTS.map(agent => (
        <Card key={agent.name} className="bg-zinc-900 border-zinc-700">
          <CardContent className="px-3 py-3 space-y-2">
            {/* Name + class */}
            <div className="flex items-center justify-between gap-1">
              <span className="text-sm font-mono font-semibold text-white">{agent.name}</span>
              <Badge variant="outline" className={`text-[10px] px-1 py-0 ${CLASS_COLOR[agent.agent_class] ?? ""}`}>
                {agent.agent_class}
              </Badge>
            </div>

            {/* HP bar */}
            <div className="space-y-0.5">
              <div className="flex justify-between text-[10px] text-zinc-400">
                <span>HP</span>
                <span className={agent.hp_status === "CRITICAL" ? "text-red-400 font-bold" : ""}>{agent.hp_pct}%</span>
              </div>
              <div className="bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${HP_BAR_COLOR[agent.hp_status]}`}
                  style={{ width: `${agent.hp_pct}%` }}
                />
              </div>
            </div>

            {/* Status */}
            <p className="text-[10px] text-zinc-400 truncate">{agent.status}</p>

            {/* Current task */}
            {agent.current_task && (
              <p className="text-[10px] text-zinc-500 italic truncate">↳ {agent.current_task}</p>
            )}

            {/* Model */}
            <p className="text-[10px] text-zinc-600 font-mono truncate">{agent.model}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
