import TaskBoard from "./TaskBoard"
import RaidLog from "./RaidLog"
import AgentLogs from "./AgentLogs"
import SprintBoard from "./SprintBoard"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

export default function Dashboard() {
  return (
    <div className="min-h-screen bg-background text-foreground p-6 space-y-6">
      <h1 className="text-2xl font-bold">Minion Comms Dashboard</h1>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="sprint">Sprint Board</TabsTrigger>
          <TabsTrigger value="tasks">Tasks</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6 mt-4">
          <section>
            <h2 className="text-lg font-semibold mb-3">Agent Logs</h2>
            <AgentLogs />
          </section>

          <section>
            <h2 className="text-lg font-semibold mb-3">Raid Log</h2>
            <RaidLog />
          </section>
        </TabsContent>

        <TabsContent value="sprint" className="mt-4">
          <SprintBoard />
        </TabsContent>

        <TabsContent value="tasks" className="mt-4">
          <TaskBoard />
        </TabsContent>
      </Tabs>
    </div>
  )
}
