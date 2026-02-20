import { useEffect, useRef } from "react"
import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

// --------------------------------------------------------------------------
// Types
// --------------------------------------------------------------------------

interface TaskDetail {
  id: number
  title: string
  status: string
  task_type: string | null
  assigned_to: string | null
  created_by: string
  project: string | null
}

interface HistoryEntry {
  from_status: string | null
  to_status: string
  agent: string
  timestamp: string
}

interface LineageData {
  task: TaskDetail
  history: HistoryEntry[]
  flow_type: string
}

interface Props {
  taskId: number
  onClose: () => void
}

// --------------------------------------------------------------------------
// Flow definition (fallback — mirrors flow_bridge.py hardcoded pipeline)
// --------------------------------------------------------------------------

const MAIN_PIPELINE = ["open", "assigned", "in_progress", "fixed", "verified", "closed"]
const DEAD_ENDS = new Set(["abandoned", "stale", "obsolete"])

function stageClass(stage: string, currentStatus: string, visitedSet: Set<string>): string {
  if (stage === currentStatus) {
    if (DEAD_ENDS.has(stage)) return "bg-orange-500/20 border-orange-500 text-orange-300 ring-2 ring-orange-500"
    return "bg-blue-500/20 border-blue-500 text-blue-300 ring-2 ring-blue-500"
  }
  if (DEAD_ENDS.has(stage)) {
    return visitedSet.has(stage)
      ? "bg-zinc-700 border-zinc-500 text-zinc-300"
      : "bg-zinc-800/40 border-zinc-700 text-zinc-600"
  }
  const pipelineIdx = MAIN_PIPELINE.indexOf(stage)
  const currentIdx = MAIN_PIPELINE.indexOf(currentStatus)
  if (pipelineIdx >= 0 && currentIdx >= 0 && pipelineIdx < currentIdx) {
    return "bg-green-900/40 border-green-700 text-green-400"
  }
  return "bg-zinc-800/40 border-zinc-700 text-zinc-500"
}

// --------------------------------------------------------------------------
// Sub-components
// --------------------------------------------------------------------------

function FlowDiagram({ currentStatus, visitedSet }: { currentStatus: string; visitedSet: Set<string> }) {
  const deadEndsInHistory = Array.from(DEAD_ENDS).filter(s => visitedSet.has(s) || s === currentStatus)

  return (
    <div className="space-y-3">
      {/* Main pipeline */}
      <div className="flex items-center gap-1 flex-wrap">
        {MAIN_PIPELINE.map((stage, i) => (
          <div key={stage} className="flex items-center gap-1">
            <span
              className={cn(
                "px-2 py-1 rounded border text-xs font-mono font-medium transition-all",
                stageClass(stage, currentStatus, visitedSet)
              )}
            >
              {stage}
            </span>
            {i < MAIN_PIPELINE.length - 1 && (
              <span className="text-zinc-600 text-xs">→</span>
            )}
          </div>
        ))}
      </div>

      {/* Dead ends (only if ever visited) */}
      {deadEndsInHistory.length > 0 && (
        <div className="flex items-center gap-2 pl-2">
          <span className="text-zinc-600 text-xs">↳ dead ends:</span>
          {deadEndsInHistory.map(stage => (
            <span
              key={stage}
              className={cn(
                "px-2 py-1 rounded border text-xs font-mono font-medium",
                stageClass(stage, currentStatus, visitedSet)
              )}
            >
              {stage}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function HistoryTimeline({ history }: { history: HistoryEntry[] }) {
  if (history.length === 0) {
    return <p className="text-zinc-500 text-sm">No history recorded.</p>
  }

  return (
    <ol className="space-y-2">
      {history.map((entry, i) => (
        <li key={i} className="flex items-start gap-3 text-sm">
          <span className="mt-0.5 w-1.5 h-1.5 rounded-full bg-zinc-500 shrink-0 mt-2" />
          <div className="flex flex-col gap-0.5">
            <span className="text-zinc-200 font-mono text-xs">
              {entry.from_status == null ? (
                <span className="text-zinc-500">(created)</span>
              ) : (
                <span className="text-zinc-400">{entry.from_status}</span>
              )}{" "}
              {entry.from_status != null && <span className="text-zinc-500">→</span>}{" "}
              <span className="font-semibold text-white">{entry.to_status}</span>
            </span>
            <span className="text-zinc-500 text-xs">
              {entry.agent} · {new Date(entry.timestamp).toLocaleString()}
            </span>
          </div>
        </li>
      ))}
    </ol>
  )
}

// --------------------------------------------------------------------------
// Main modal
// --------------------------------------------------------------------------

export default function TaskLineageModal({ taskId, onClose }: Props) {
  const { data, isLoading } = useSWR<LineageData>(`/api/task-lineage/${taskId}`, fetcher)
  const overlayRef = useRef<HTMLDivElement>(null)

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [onClose])

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === overlayRef.current) onClose()
  }

  const visitedSet = new Set(data?.history.map(h => h.to_status) ?? [])

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    >
      <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-lg border border-zinc-700 bg-zinc-900 shadow-xl p-6 m-4">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-zinc-400 hover:text-white text-lg leading-none"
          aria-label="Close"
        >
          ✕
        </button>

        {isLoading && (
          <p className="text-zinc-500 text-sm">Loading lineage...</p>
        )}

        {data && (
          <div className="space-y-6">
            {/* Task header */}
            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-zinc-500 font-mono text-xs">#{data.task.id}</span>
                <Badge variant="outline" className="text-xs">
                  {data.task.task_type ?? "bugfix"}
                </Badge>
                <Badge
                  className={cn(
                    "text-xs",
                    DEAD_ENDS.has(data.task.status)
                      ? "bg-orange-500/20 border-orange-500 text-orange-300"
                      : data.task.status === "closed"
                      ? "bg-green-900/40 border-green-700 text-green-400"
                      : "bg-blue-500/20 border-blue-500 text-blue-300"
                  )}
                  variant="outline"
                >
                  {data.task.status}
                </Badge>
              </div>
              <h2 className="text-white font-semibold text-base leading-snug">{data.task.title}</h2>
              <div className="text-zinc-500 text-xs flex gap-4">
                <span>assigned: <span className="text-zinc-300">{data.task.assigned_to ?? "—"}</span></span>
                {data.task.project && (
                  <span>project: <span className="text-zinc-300">{data.task.project}</span></span>
                )}
              </div>
            </div>

            {/* DAG */}
            <div className="space-y-2">
              <h3 className="text-zinc-400 text-xs font-semibold uppercase tracking-wider">
                Flow · {data.flow_type}
              </h3>
              <FlowDiagram currentStatus={data.task.status} visitedSet={visitedSet} />
            </div>

            {/* History */}
            <div className="space-y-2">
              <h3 className="text-zinc-400 text-xs font-semibold uppercase tracking-wider">
                History · {data.history.length} transition{data.history.length !== 1 ? "s" : ""}
              </h3>
              <HistoryTimeline history={data.history} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
