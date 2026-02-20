import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

interface Phase {
  phase: string
  owner: string
  status: string
  artifact: string
}

interface SprintData {
  sprint: string | null
  phases: Phase[]
}

const statusVariant: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  pending: "secondary",
  "in-progress": "default",
  done: "outline",
  blocked: "destructive",
}

export default function SprintBoard() {
  const { data, isLoading } = useSWR<SprintData>("/api/sprint", fetcher, {
    refreshInterval: 5000,
  })

  if (isLoading) return <p className="text-muted-foreground">Loading sprint...</p>
  if (!data?.sprint) return <p className="text-muted-foreground">No active sprint</p>

  return (
    <div className="space-y-3">
      <h3 className="text-md font-semibold">{data.sprint}</h3>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Phase</TableHead>
            <TableHead>Owner</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Artifact</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.phases.map((p) => (
            <TableRow key={p.phase}>
              <TableCell className="font-medium">{p.phase}</TableCell>
              <TableCell>{p.owner}</TableCell>
              <TableCell>
                <Badge variant={statusVariant[p.status] ?? "secondary"}>
                  {p.status}
                </Badge>
              </TableCell>
              <TableCell className="text-muted-foreground">
                {p.artifact || "\u2014"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
