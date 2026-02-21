import express from 'express';
import Database from 'better-sqlite3';
import crypto from 'crypto';
import fs from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';
import os from 'os';
import yaml from 'js-yaml';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dbPath = process.env.MINION_DB_PATH || path.join(os.homedir(), '.minion_work', process.env.MINION_PROJECT || 'default', 'minion.db');
const db = new Database(dbPath, { readonly: true });

const app = express();
app.use(express.json());
const PORT = 3001;

// Auth: simple token-based login
const SESSION_SECRET = crypto.randomBytes(32).toString('hex');
const activeSessions = new Set();

app.post('/api/login', (req, res) => {
  const { username, password } = req.body;
  if (username === 'admin' && password === 'admin') {
    const token = crypto.randomBytes(24).toString('hex');
    activeSessions.add(token);
    return res.json({ ok: true, token });
  }
  res.status(401).json({ ok: false, error: 'Invalid credentials' });
});

// Auth middleware for all other /api routes
function requireAuth(req, res, next) {
  const auth = req.headers.authorization;
  if (!auth || !auth.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  const token = auth.slice(7);
  if (!activeSessions.has(token)) {
    return res.status(401).json({ error: 'Invalid session' });
  }
  next();
}

app.use('/api/agents', requireAuth);
app.use('/api/tasks', requireAuth);
app.use('/api/raid-log', requireAuth);
app.use('/api/logs', requireAuth);
app.use('/api/task-lineage', requireAuth);
app.use('/api/messages', requireAuth);
app.use('/api/flows', requireAuth);

app.get('/api/agents', (_req, res) => {
  const rows = db.prepare(`
    SELECT a.name, a.agent_class, a.model, a.status, a.transport,
           a.hp_input_tokens, a.hp_output_tokens, a.hp_tokens_limit,
           a.hp_turn_input, a.hp_turn_output, a.hp_updated_at,
           a.last_seen, a.context_summary, a.current_zone, a.current_role, a.registered_at,
           t.id AS task_id, t.title AS task_title, t.status AS task_status
    FROM agents a
    LEFT JOIN tasks t ON t.assigned_to = a.name AND t.status = 'in_progress'
    ORDER BY a.last_seen DESC
  `).all();

  const agents = rows.map(row => {
    // Prefer per-turn input (actual context pressure); fall back to cumulative capped at limit
    const raw = row.hp_turn_input ?? row.hp_input_tokens;
    const used = row.hp_tokens_limit ? Math.min(raw ?? 0, row.hp_tokens_limit) : raw;
    const hp_pct = row.hp_tokens_limit && used
      ? Math.max(0, Math.round(100 - (used / row.hp_tokens_limit * 100)))
      : null;
    let hp_status = null;
    if (hp_pct !== null) {
      hp_status = hp_pct > 50 ? 'Healthy' : hp_pct > 25 ? 'Wounded' : 'CRITICAL';
    }
    const current_task = row.task_id
      ? { id: row.task_id, title: row.task_title, status: row.task_status }
      : null;
    const { task_id, task_title, task_status, ...agent } = row;
    return { ...agent, hp_pct, hp_status, current_task };
  });

  res.json(agents);
});

app.get('/api/tasks', (_req, res) => {
  const rows = db.prepare(`
    SELECT id, title, status, assigned_to, created_by, project, zone,
           blocked_by, activity_count, progress, created_at, updated_at
    FROM tasks ORDER BY updated_at DESC
  `).all();
  res.json(rows);
});

app.get('/api/task-lineage/:id', (req, res) => {
  const taskId = parseInt(req.params.id);
  if (isNaN(taskId)) return res.status(400).json({ error: 'Invalid task ID' });

  const task = db.prepare('SELECT * FROM tasks WHERE id = ?').get(taskId);
  if (!task) return res.status(404).json({ error: 'Task not found' });

  const history = db.prepare(
    'SELECT from_status, to_status, agent, timestamp FROM task_history WHERE task_id = ? ORDER BY timestamp ASC'
  ).all(taskId);

  res.json({ task, history, flow_type: task.task_type || 'bugfix' });
});

app.get('/api/raid-log', (_req, res) => {
  const rows = db.prepare(`
    SELECT id, agent_name, entry_file, priority, created_at
    FROM raid_log ORDER BY created_at DESC
  `).all();

  const entries = rows.map(row => {
    let content = '';
    try {
      content = fs.readFileSync(row.entry_file, 'utf-8');
    } catch {
      content = '(file not found)';
    }
    return { ...row, content };
  });

  res.json(entries);
});

// Sprint board data
const sprintFile = path.join(__dirname, '..', '.minion-swarm', 'sprint.json');
app.use('/api/sprint', requireAuth);
app.get('/api/sprint', (_req, res) => {
  try {
    const data = JSON.parse(fs.readFileSync(sprintFile, 'utf-8'));
    res.json(data);
  } catch {
    res.json({ sprint: null, phases: [] });
  }
});

// Agent terminal logs from minion-swarm
// Logs are in the project root's .minion-swarm/logs/
const logsDir = path.join(__dirname, '..', '.minion-swarm', 'logs');

app.get('/api/logs', (_req, res) => {
  try {
    const files = fs.readdirSync(logsDir).filter(f => f.endsWith('.log'));
    const logs = {};
    for (const file of files) {
      const name = file.replace('.log', '');
      const content = fs.readFileSync(path.join(logsDir, file), 'utf-8');
      const lines = content.split('\n');
      // Return last 200 lines to keep payload reasonable
      logs[name] = lines.slice(-200).join('\n');
    }
    res.json(logs);
  } catch {
    res.json({});
  }
});

app.get('/api/logs/:agent', (req, res) => {
  const agentName = req.params.agent.replace(/[^a-zA-Z0-9_-]/g, '');
  const logFile = path.join(logsDir, `${agentName}.log`);
  try {
    const content = fs.readFileSync(logFile, 'utf-8');
    const lines = content.split('\n');
    const tail = parseInt(req.query.tail) || 100;
    res.json({ agent: agentName, lines: lines.slice(-tail) });
  } catch {
    res.json({ agent: agentName, lines: ['(no log file found)'] });
  }
});

// Recent messages — content is read from disk and truncated to 200 chars for feed display
app.get('/api/messages', (req, res) => {
  const limit = Math.min(parseInt(req.query.limit) || 50, 200);
  const rows = db.prepare(`
    SELECT id, from_agent, to_agent, content_file, timestamp, read_flag, is_cc
    FROM messages ORDER BY timestamp DESC LIMIT ?
  `).all(limit);

  const messages = rows.map(row => {
    let content = '';
    try {
      const raw = fs.readFileSync(row.content_file, 'utf-8');
      content = raw.length > 200 ? raw.slice(0, 200) + '…' : raw;
    } catch {
      content = '(file not found)';
    }
    return { ...row, content };
  });

  res.json(messages);
});

// Flow definitions — load YAML from missions/ dir, return as JSON
const missionsDir = path.join(__dirname, '..', 'missions');

app.get('/api/flows/:type', (req, res) => {
  const type = req.params.type.replace(/[^a-zA-Z0-9_-]/g, '');
  const filePath = path.join(missionsDir, `${type}.yaml`);
  const raw = fs.readFileSync(filePath, 'utf-8');
  const data = yaml.load(raw);
  res.json(data);
});

// Serve static files from dist/ in production
app.use(express.static(path.join(__dirname, 'dist')));

app.listen(PORT, () => {
  console.log(`API server listening on http://localhost:${PORT}`);
});
