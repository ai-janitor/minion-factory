import { useState } from "react"
import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import { Badge } from "@/components/ui/badge"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import TaskLineageModal from "@/components/TaskLineageModal"

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
  created_at: string
  updated_at: string
}

function statusVariant(status: string) {
  switch (status) {
    case "done": return "secondary" as const
    case "in-progress": return "default" as const
    case "blocked": return "destructive" as const
    default: return "outline" as const
  }
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export default function TaskBoard() {
  const { data: tasks } = useSWR<Task[]>("/api/tasks", fetcher, { refreshInterval: 5000 })
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null)

  if (!tasks) return <div className="text-muted-foreground p-4">Loading tasks...</div>

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">ID</TableHead>
            <TableHead>Title</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Assigned</TableHead>
            <TableHead className="w-16">Activity</TableHead>
            <TableHead>Updated</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tasks.map(task => (
            <TableRow
              key={task.id}
              className="cursor-pointer hover:bg-muted/50"
              onClick={() => setSelectedTaskId(task.id)}
            >
              <TableCell className="font-mono text-xs">#{task.id}</TableCell>
              <TableCell className="max-w-64 truncate">{task.title}</TableCell>
              <TableCell>
                <Badge variant={statusVariant(task.status)}>{task.status}</Badge>
              </TableCell>
              <TableCell className="text-xs">{task.assigned_to ?? "—"}</TableCell>
              <TableCell className="text-center text-xs">{task.activity_count}</TableCell>
              <TableCell className="text-xs text-muted-foreground">{relativeTime(task.updated_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {selectedTaskId !== null && (
        <TaskLineageModal
          taskId={selectedTaskId}
          onClose={() => setSelectedTaskId(null)}
        />
      )}
    </>
  )
}
