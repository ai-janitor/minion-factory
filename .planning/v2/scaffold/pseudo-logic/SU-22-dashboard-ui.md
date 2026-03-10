# SU-22 Pseudo-Logic: Dashboard UI Consolidation

## NEW: src/minion/network/templates/dashboard/

### base.html
```html
<!-- Minimal base template:
  - HTML5 doctype
  - Inline CSS: system fonts, responsive tables, color-coded status badges
  - Meta refresh every 30s for auto-update
  - Nav links: Agents | Tasks | Health | Messages
  - Block: {% block content %}{% endblock %}
-->
```

### agents.html (extends base.html)
```html
<!-- Agent health dashboard:
  - Table: name, class, status, HP bar, last_seen, current task, unread count
  - Color coding:
    - HP >= 75: green
    - HP >= 50: yellow
    - HP < 50: red
    - last_seen > 5 min: gray (stale)
  - Data from: dashboard/queries.py get_agent_summary()
-->
```

### tasks.html (extends base.html)
```html
<!-- Task pipeline:
  - Kanban columns: open, assigned, in_progress, fixed, qe, verify, closed
  - Each card: task ID, title (truncated), assigned agent, time in status
  - Filter controls: agent dropdown, flow_type dropdown
  - Data from: dashboard/queries.py get_task_pipeline()
-->
```

### health.html (extends base.html)
```html
<!-- System health:
  - DB stats: file size, row counts per table, WAL status
  - Agent stats: total, active (last_seen < 5 min), stale, by class
  - Message stats: total, unread, avg delivery time
  - Battle plan: active plan name and progress
  - Data from: dashboard/queries.py get_system_stats()
-->
```

### messages.html (extends base.html)
```html
<!-- Message flow:
  - Table: timestamp, from, to, msg_type badge, read/unread icon
  - Last 50 messages, newest first
  - Filter: agent, msg_type dropdown, read status toggle
  - Data from: dashboard/queries.py get_recent_messages()
-->
```

## MODIFY: src/minion/dashboard/queries.py

```python
# Add/extend query functions:

def get_agent_summary(db) -> list[dict]:
    """Query all agents with health data.
    # SELECT a.name, a.class, a.status, a.hp, a.last_seen,
    #        t.title as current_task,
    #        (SELECT COUNT(*) FROM messages WHERE to_agent=a.name AND read_flag=0) as unread
    # FROM agents a LEFT JOIN tasks t ON t.assigned_to = a.name AND t.status NOT IN terminal
    """

def get_task_pipeline(db) -> dict[str, list[dict]]:
    """Query tasks grouped by status.
    # SELECT * FROM tasks ORDER BY updated_at DESC
    # Group by status into: {status: [task_dicts]}
    """

def get_system_stats(db) -> dict:
    """Query DB and system stats.
    # DB size: os.path.getsize(db_path)
    # Row counts: SELECT COUNT(*) FROM <table> for each table
    # WAL: PRAGMA journal_mode
    # Agent counts: total, active (last_seen < 5 min ago), stale
    """

def get_recent_messages(db, limit=50) -> list[dict]:
    """Query recent messages.
    # SELECT * FROM messages ORDER BY timestamp DESC LIMIT ?
    """
```

## MODIFY: src/minion/network/dashboard.py

```python
# Wire dashboard routes to Jinja2 rendering:
#
# from jinja2 import Environment, FileSystemLoader
# templates = Environment(loader=FileSystemLoader("src/minion/network/templates"))
#
# async def dashboard_index(request):
#     return render_template("dashboard/agents.html", agents=get_agent_summary(db))
#
# async def dashboard_agents(request):
#     return render_template("dashboard/agents.html", agents=get_agent_summary(db))
#
# async def dashboard_tasks(request):
#     return render_template("dashboard/tasks.html", pipeline=get_task_pipeline(db))
#
# async def dashboard_health(request):
#     return render_template("dashboard/health.html", stats=get_system_stats(db))
#
# async def dashboard_messages(request):
#     return render_template("dashboard/messages.html", messages=get_recent_messages(db))
```

## MODIFY: src/minion/network/router.py

```python
# Register dashboard routes:
# router.add_route("GET", "/dashboard/", dashboard.dashboard_index)
# router.add_route("GET", "/dashboard/agents", dashboard.dashboard_agents)
# router.add_route("GET", "/dashboard/tasks", dashboard.dashboard_tasks)
# router.add_route("GET", "/dashboard/health", dashboard.dashboard_health)
# router.add_route("GET", "/dashboard/messages", dashboard.dashboard_messages)
```

## MODIFY: pyproject.toml

```toml
# Add jinja2 dependency if not present:
# [project.dependencies]
# jinja2 >= 3.0
```
