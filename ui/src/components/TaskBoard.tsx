// Kanban board — tasks grouped into 6 status columns. Replaces the flat table
// so at-a-glance flow state is visible without opening individual tasks.
import { useState } from "react"
import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import TaskLineageModal from "@/components/TaskLineageModal"

// --------------------------------------------------------------------------
// Types
// --------------------------------------------------------------------------

interface Task {
  id: number
  title: string
  status: string
  assigned_to: string | null
  created_by: string
  project: string | null
  zone: string | null
  blocked_by: string | null
  activity_count: number
  progress: string | null
  priority: string | null
  class_required: string | null
  created_at: string
  updated_at: string
}

// --------------------------------------------------------------------------
// Constants
// --------------------------------------------------------------------------

const COLUMNS: { status: string; label: string; headerClass: string }[] = [
  { status: "open",        label: "Open",        headerClass: "text-zinc-400 border-zinc-700" },
  { status: "assigned",    label: "Assigned",    headerClass: "text-blue-400 border-blue-800" },
  { status: "in_progress", label: "In Progress", headerClass: "text-yellow-400 border-yellow-800" },
  { status: "fixed",       label: "Fixed",       headerClass: "text-purple-400 border-purple-800" },
  { status: "verified",    label: "Verified",    headerClass: "text-green-400 border-green-800" },
  { status: "closed",      label: "Closed",      headerClass: "text-zinc-500 border-zinc-800" },
]

const PRIORITY_COLORS: Record<string, string> = {
  critical: "bg-red-500/20 text-red-400 border-red-700",
  high:     "bg-orange-500/20 text-orange-400 border-orange-700",
  normal:   "bg-zinc-700/40 text-zinc-400 border-zinc-600",
  low:      "bg-zinc-800/40 text-zinc-500 border-zinc-700",
}

// --------------------------------------------------------------------------
// TaskCard
// --------------------------------------------------------------------------

function TaskCard({ task, onClick }: { task: Task; onClick: () => void }) {
  const priorityClass = PRIORITY_COLORS[task.priority ?? "normal"] ?? PRIORITY_COLORS.normal

  return (
    <Card
      onClick={onClick}
      className="cursor-pointer hover:border-zinc-500 transition-colors bg-zinc-900 border-zinc-700 py-3 gap-2"
    >
      <CardContent className="px-3 space-y-2">
        {/* Title + ID */}
        <div className="flex items-start justify-between gap-1">
          <span className="text-xs text-white font-medium leading-snug line-clamp-2">
            {task.title}
          </span>
          <span className="text-zinc-600 font-mono text-[10px] shrink-0">#{task.id}</span>
        </div>

        {/* Meta row */}
        <div className="flex flex-wrap gap-1 items-center">
          {/* Priority — skip 'normal' to reduce noise */}
          {task.priority && task.priority !== "normal" && (
            <Badge variant="outline" className={`text-[10px] px-1 py-0 ${priorityClass}`}>
              {task.priority}
            </Badge>
          )}

          {/* Class required */}
          {task.class_required && (
            <Badge variant="outline" className="text-[10px] px-1 py-0 text-zinc-400 border-zinc-600">
              {task.class_required}
            </Badge>
          )}

          {/* Assigned agent */}
          {task.assigned_to && (
            <span className="text-[10px] text-zinc-500 font-mono truncate max-w-[80px]">
              @{task.assigned_to}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

// --------------------------------------------------------------------------
// KanbanColumn
// --------------------------------------------------------------------------

function KanbanColumn({
  status: _status, label, headerClass, tasks, onCardClick,
}: {
  status: string
  label: string
  headerClass: string
  tasks: Task[]
  onCardClick: (id: number) => void
}) {
  return (
    <div className="flex flex-col min-w-[200px] flex-1 max-w-[280px]">
      {/* Column header */}
      <div className={`flex items-center justify-between px-2 py-1.5 mb-2 rounded border ${headerClass}`}>
        <span className="text-xs font-semibold uppercase tracking-wider">{label}</span>
        <span className="text-[10px] font-mono opacity-60">{tasks.length}</span>
      </div>

      {/* Cards — scrollable independently */}
      <div className="flex-1 overflow-y-auto space-y-2 pr-0.5" style={{ maxHeight: "calc(100vh - 180px)" }}>
        {tasks.length === 0 && (
          <div className="text-zinc-700 text-xs text-center py-4">—</div>
        )}
        {tasks.map(task => (
          <TaskCard key={task.id} task={task} onClick={() => onCardClick(task.id)} />
        ))}
      </div>
    </div>
  )
}

// --------------------------------------------------------------------------
// TaskBoard (kanban root)
// --------------------------------------------------------------------------

export default function TaskBoard() {
  const { data: tasks } = useSWR<Task[]>("/api/tasks", fetcher, { refreshInterval: 5000 })
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null)

  if (!tasks) return <div className="text-muted-foreground p-4">Loading tasks...</div>

  // Bucket tasks into columns; unknown statuses fall into the nearest bucket or are ignored
  const byStatus = Object.fromEntries(COLUMNS.map(c => [c.status, [] as Task[]]))
  for (const task of tasks) {
    if (byStatus[task.status]) {
      byStatus[task.status].push(task)
    }
  }

  return (
    <>
      {/* Columns wrap on small screens via flex-wrap */}
      <div className="flex gap-3 overflow-x-auto pb-2 flex-wrap">
        {COLUMNS.map(col => (
          <KanbanColumn
            key={col.status}
            status={col.status}
            label={col.label}
            headerClass={col.headerClass}
            tasks={byStatus[col.status]}
            onCardClick={setSelectedTaskId}
          />
        ))}
      </div>

      {selectedTaskId !== null && (
        <TaskLineageModal
          taskId={selectedTaskId}
          onClose={() => setSelectedTaskId(null)}
        />
      )}
    </>
  )
}
