# Agent Teams — Master Reference Guide

> Source: https://code.claude.com/docs/en/agent-teams  
> Claude Code v2.1.32+ required. Feature is experimental — enabled via `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.

---

## What Agent Teams Are

A **team** is a group of independent Claude Code sessions working together on a shared task list. One session is the **lead** (the orchestrator). The rest are **teammates** (workers). Each teammate has its own full context window and can communicate directly with other teammates — not just report back to the lead.

This is the key difference from subagents.

---

## Agent Teams vs. Subagents — When to Use Which

| Dimension | Subagents | Agent Teams |
|-----------|-----------|-------------|
| Context | Own window; results summarized back | Own window; fully independent |
| Communication | Report to lead only | Message each other directly |
| Coordination | Lead manages everything | Shared task list + self-coordination |
| Token cost | Lower | Significantly higher |
| Best for | Focused tasks where only the result matters | Complex work requiring discussion, debate, or collaboration |
| Use when | Sequential tasks, same-file edits, many dependencies | Parallel exploration, competing hypotheses, cross-layer changes |

**Rule of thumb:** if teammates don't need to talk to each other, use subagents. If they need to share findings, challenge each other, or coordinate independently — use an agent team.

---

## Enabling Agent Teams

In `.claude/settings.local.json` (project-level) or `~/.claude.json` (global):

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

Or export directly in the shell:
```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                     TEAM LEAD                       │
│  Creates team · Assigns tasks · Synthesizes results │
└──────────┬──────────────┬──────────────┬────────────┘
           │              │              │
    ┌──────▼─────┐ ┌──────▼─────┐ ┌─────▼──────┐
    │ Teammate A │ │ Teammate B │ │ Teammate C │
    │ Own context│ │ Own context│ │ Own context│
    └──────┬─────┘ └──────┬─────┘ └─────┬──────┘
           │              │              │
           └──────────────▼──────────────┘
                   Shared Task List
                   + Mailbox (direct messaging)
```

**Key components:**

| Component | Role |
|-----------|------|
| **Team lead** | Creates the team, spawns teammates, manages task list |
| **Teammates** | Independent Claude instances, each own context window |
| **Task list** | Shared work queue; teammates self-claim or are assigned tasks |
| **Mailbox** | Message bus for direct agent-to-agent communication |

**Storage (local, auto-managed — do not edit by hand):**
- Team config: `~/.claude/teams/{team-name}/config.json`
- Task list: `~/.claude/tasks/{team-name}/`

---

## Display Modes

| Mode | How it works | When to use |
|------|-------------|-------------|
| `in-process` | All teammates in main terminal. `Shift+Down` to cycle. | Any terminal, default fallback |
| `tmux` / split panes | Each teammate in own pane. Click to interact. | When inside a tmux session or iTerm2 |
| `auto` (default) | Split panes if already in tmux, in-process otherwise | Default |

Override globally in `~/.claude.json`:
```json
{ "teammateMode": "in-process" }
```

Or per-session:
```bash
claude --teammate-mode in-process
```

**Split pane requirements:** tmux (via package manager) or iTerm2 with `it2` CLI + Python API enabled.  
**Known:** tmux works best on macOS. Not supported in VS Code terminal, Windows Terminal, or Ghostty.

---

## Starting a Team

Just describe the task and structure in natural language. Claude decides team size unless you specify:

```
Create an agent team to explore this from different angles:
one teammate on UX, one on technical architecture, one playing devil's advocate.
```

To specify size and model:
```
Create a team with 4 teammates to refactor these modules in parallel.
Use Sonnet for each teammate.
```

Claude won't create a team without your approval.

---

## Controlling the Team

### Talk to teammates directly
- **In-process:** `Shift+Down` to cycle through teammates → type to message → `Enter` to view session → `Escape` to interrupt
- **Split pane:** click into any pane
- `Ctrl+T` toggles the task list

### Assign tasks
```
Assign the auth refactor task to Teammate A.
```
Or let teammates self-claim — when they finish a task, they pick up the next unblocked one automatically. File locking prevents race conditions.

### Require plan approval before implementation
```
Spawn an architect teammate to refactor the auth module.
Require plan approval before they make any changes.
```
Teammate stays in read-only plan mode → submits plan to lead → lead approves or rejects with feedback → implementation begins on approval.

Set lead's criteria upfront: "only approve plans that include test coverage."

### Shut down a teammate
```
Ask the researcher teammate to shut down.
```
Teammate can accept (exits gracefully) or reject with explanation.

### Clean up the whole team
```
Clean up the team.
```
**Always clean up via the lead.** Teammates should not run cleanup — their team context may not resolve correctly, leaving orphaned resources. Lead checks for active teammates and fails if any are still running (shut them down first).

---

## Context & Communication Rules

**What teammates inherit at spawn:**
- Project `CLAUDE.md` files (full, from working directory)
- MCP servers configured for the project
- Project skills
- The spawn prompt from the lead

**What teammates do NOT inherit:**
- The lead's conversation history
- Any context built up during the current session

**Implication:** include all task-specific context in the spawn prompt. Don't assume a teammate "knows" what the lead discussed earlier.

**Messaging mechanics:**
- `message` — send to one specific teammate
- `broadcast` — send to all teammates simultaneously (use sparingly — cost scales with team size)
- Idle notifications are automatic — when a teammate finishes, the lead is notified automatically

---

## Reusable Teammate Roles (Subagent Definitions)

Define a role once in `.claude/skills/` and reference it when spawning:

```
Spawn a teammate using the security-reviewer agent type to audit the auth module.
```

Teammate inherits that subagent's system prompt, tools, and model. Works with any subagent scope: project, user, plugin, or CLI-defined.

---

## Hooks for Quality Gates

Three hooks enforce rules during team execution:

| Hook | When it fires | Exit code 2 effect |
|------|--------------|-------------------|
| `TeammateIdle` | Teammate is about to go idle | Sends feedback, keeps teammate working |
| `TaskCreated` | A task is being created | Prevents creation, sends feedback |
| `TaskCompleted` | A task is being marked complete | Prevents completion, sends feedback |

Use these to enforce standards like "no task marked complete without tests" or "all plans must include a rollback section."

---

## Permissions

- Teammates start with the **lead's permission settings**
- If lead runs `--dangerously-skip-permissions`, all teammates do too
- You can change individual teammate modes **after** spawning, but not at spawn time
- Permission requests from teammates bubble up to the lead — pre-approve common operations before spawning to reduce friction

---

## Token Cost Considerations

- Each teammate = a separate Claude instance = its own token budget
- Cost scales linearly with team size
- Broadcast messages are expensive — each message costs tokens for every recipient
- **When the cost is worth it:** research, review, competing hypotheses, cross-layer work
- **When it's not:** routine tasks, sequential work, single-file edits

---

## Best Practices

### Team size
- **Start with 3–5 teammates** for most workflows
- Aim for **5–6 tasks per teammate** — keeps everyone productive without excessive context switching
- Scale up only when the work genuinely benefits from simultaneous parallel progress
- Three focused teammates often outperform five scattered ones

### Task sizing
| Size | Problem | Signal |
|------|---------|--------|
| Too small | Coordination overhead exceeds benefit | Tasks complete in under 2 minutes |
| Too large | Long periods without check-ins, wasted effort | Tasks take more than 30–60 minutes |
| Just right | Self-contained unit with a clear deliverable | A function, test file, review section |

### Spawn prompts
Give teammates everything they need in the spawn prompt — they won't know what the lead discussed. Include:
- The specific files or areas to work in
- The exact objective and deliverable
- Any domain constraints (e.g. "JWT tokens stored in httpOnly cookies")
- How to report findings

```
Spawn a security reviewer teammate with the prompt:
"Review src/auth/ for security vulnerabilities. Focus on token handling,
session management, and input validation. The app uses JWT tokens stored in
httpOnly cookies. Report issues with severity ratings (Critical/High/Medium/Low)."
```

### Avoid file conflicts
Two teammates editing the same file = overwrites. Design the task breakdown so each teammate **owns a distinct set of files**. Never have two teammates work on the same module simultaneously.

### Monitor and steer
- Check in regularly — don't let a team run unattended for long
- Redirect teammates that are going in the wrong direction early
- Synthesize findings as they come in, not just at the end

### Use the debate pattern for investigations
When root cause is unclear, make teammates explicitly adversarial:
```
Spawn 5 teammates to investigate different hypotheses. Have them talk to each
other and try to disprove each other's theories. Update a shared findings doc
with whatever consensus emerges.
```
Sequential investigation anchors on the first plausible theory. Parallel debate forces the survivors to be genuinely robust.

### Start with research/review before parallel implementation
If new to agent teams — start with review, research, or investigation tasks. These have natural boundaries, don't risk file conflicts, and show the value of parallel exploration clearly.

---

## Strongest Use Cases

| Use Case | Why teams excel |
|----------|----------------|
| **Parallel code review** | Each reviewer applies a different lens (security, performance, tests) simultaneously — no anchoring |
| **Competing hypothesis debugging** | Multiple independent investigators actively trying to disprove each other → more robust root cause |
| **New feature modules** | Each teammate owns a separate module — no file conflicts, truly parallel |
| **Cross-layer coordination** | Frontend, backend, and tests each owned by a different teammate |
| **CIM/document analysis** | Multiple analysts extract different sections simultaneously |
| **Multi-perspective design** | UX, architecture, and devil's advocate exploring a problem in parallel |

---

## Limitations (Experimental)

| Limitation | Workaround |
|-----------|------------|
| No `/resume` or `/rewind` for in-process teammates | After resuming, tell lead to spawn new teammates |
| Task status can lag (stuck tasks block dependents) | Manually update task status or tell lead to nudge the teammate |
| Slow shutdown (finishes current call before exiting) | Plan for it; don't assume immediate termination |
| One team per lead session | Clean up before starting a new team |
| No nested teams | Teammates cannot spawn their own teams |
| Lead is fixed for team lifetime | Cannot promote a teammate to lead |
| Per-teammate permissions set at spawn only | Change modes after spawning if needed |
| Split panes: no VS Code terminal, Windows Terminal, Ghostty | Use in-process mode on those terminals |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Teammates not appearing | Press `Shift+Down` — they may be running but not visible. Check if task was complex enough to warrant a team. Verify `tmux` in PATH if using split panes. |
| Too many permission prompts | Pre-approve common operations in permissions settings before spawning |
| Teammate stops on error | `Shift+Down` to reach it, give new instructions, or spawn a replacement |
| Lead shuts down before work is done | "Keep going" or "Wait for teammates to finish before proceeding" |
| Orphaned tmux sessions | `tmux ls` then `tmux kill-session -t <name>` |

---

## LBO Project — Recommended Team Pattern

For this multi-agent LBO model system, the optimal team structure is:

```
Lead (Orchestrator)
├── Parser Agent       → data_parser.parse_document()
├── Domain Agent       → lbo_engine.generate_instructions()
└── Excel Agent        → advanced_excel.batch_write()
```

**Spawn prompt pattern for the Excel Agent:**
```
Spawn an Excel agent teammate. Load advanced_excel.py and execute the
batch_write instructions provided in the task. Do not modify any formula
cells unless force=True is set. Save and produce the audit log when done.
The template is IOI Model Template.xlsx; output to output/LBO_populated.xlsx.
```

**Key constraint:** these three agents are sequential (output of one feeds the next), so a standard subagent pipeline is actually more appropriate than a full team — unless you are running multiple deals in parallel, in which case spawn one full pipeline team per deal.

---

## Quick Reference Card

```bash
# Enable
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

# Minimum version
claude --version  # must be >= 2.1.32

# Create team (natural language)
"Create an agent team with 3 teammates: one for X, one for Y, one for Z."

# Navigate teammates (in-process)
Shift+Down     # cycle to next teammate
Ctrl+T         # toggle task list
Escape         # interrupt current turn

# Lifecycle
"Assign task X to Teammate A"
"Ask Teammate B to shut down"
"Clean up the team"          # always via lead

# Display mode override
claude --teammate-mode in-process

# Fix orphaned sessions
tmux ls
tmux kill-session -t <name>
```
