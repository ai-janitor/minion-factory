// Main dashboard layout — tabs for Tasks, Messages, Agents views
// Agent panel always visible at top; main content area switches by tab
import TaskBoard from "./TaskBoard"
import RaidLog from "./RaidLog"
import AgentLogs from "./AgentLogs"
import SprintBoard from "./SprintBoard"
import AgentPanel from "./AgentPanel"
import MessageFeed from "./MessageFeed"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

export default function Dashboard() {
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      {/* Top bar */}
      <header className="border-b border-zinc-800 px-6 py-3 flex items-center gap-3">
        <span className="text-lg font-bold font-mono tracking-tight">minion-comms</span>
        <span className="text-xs text-zinc-500 font-mono">mission control</span>
      </header>

      <div className="flex-1 flex flex-col p-4 space-y-4 max-w-[1600px] mx-auto w-full">
        {/* Agent panel — always visible at top */}
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-2">Agents</h2>
          <AgentPanel />
        </section>

        {/* Main tabbed content area */}
        <Tabs defaultValue="tasks" className="flex-1">
          <TabsList className="mb-3">
            <TabsTrigger value="tasks">Tasks</TabsTrigger>
            <TabsTrigger value="messages">Messages</TabsTrigger>
            <TabsTrigger value="overview">Logs</TabsTrigger>
            <TabsTrigger value="sprint">Sprint</TabsTrigger>
          </TabsList>

          {/* Kanban board */}
          <TabsContent value="tasks" className="mt-0">
            <TaskBoard />
          </TabsContent>

          {/* Live message feed */}
          <TabsContent value="messages" className="mt-0">
            <section className="space-y-2">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Message Feed</h2>
              <MessageFeed />
            </section>
          </TabsContent>

          {/* Live logs + raid log */}
          <TabsContent value="overview" className="space-y-6 mt-0">
            <section>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-2">Agent Logs</h2>
              <AgentLogs />
            </section>
            <section>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-2">Raid Log</h2>
              <RaidLog />
            </section>
          </TabsContent>

          <TabsContent value="sprint" className="mt-0">
            <SprintBoard />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
