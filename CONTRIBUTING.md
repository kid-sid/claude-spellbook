# Contributing to claude-spellbook

Contributions are welcome. This guide covers how to add or fix skills, agents, slash commands, and tool configs.

---

## Ways to contribute

| Type | What to do |
|---|---|
| **New skill** | Create `skills/<name>/skill.md` following the format below |
| **New agent** | Create `.claude/agents/<name>.md` following the agent format |
| **New slash command** | Create `.claude/commands/<name>.md` |
| **New tool config** | Add a language directory under `tools/` and wire it into `install.sh` |
| **Bug fix or improvement** | Open an issue first if it's non-trivial; small fixes can go straight to PR |
| **Skill request (no code)** | Open an issue with the **New Skill Request** template |

---

## Setup

```bash
git clone https://github.com/sidharthamohanty/claude-spellbook
cd claude-spellbook
make install   # install Node + Python tools (prettier, markdownlint, ruff, black)
make check     # verify tools are on PATH
```

---

## Branch and commit conventions

```
feat/skill-<name>       # new skill
feat/agent-<name>       # new agent
feat/command-<name>     # new slash command
fix/<issue-or-topic>    # bug fix
docs/<topic>            # documentation only
chore/<topic>           # CI, tooling, housekeeping
```

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add accessibility-testing skill
fix: correct api-design checklist item for pagination
docs: clarify skill installation steps in README
chore: bump markdownlint to 0.39
```

---

## Adding a skill

Every skill file lives at `skills/<name>/skill.md` and must follow this exact structure — CI will reject anything that deviates:

```markdown
---
name: kebab-case-name
description: One dense keyword-rich sentence.
---

# Title

One-sentence intro.

## When to Activate
- Verb-leading trigger condition (6–8 items)

## <Content sections using ## and ###>

## Checklist
- [ ] At least 8 items, written from a "before you ship" perspective
```

**Format rules:**

- `name` in frontmatter must match the folder name exactly
- `## When to Activate` and `## Checklist` sections are required
- Checklist must have at least one `- [ ]` item
- Language-agnostic topics: show Python, TypeScript, and Go as siblings
- Tool-specific content (GitHub Actions, Terraform, Dockerfile): native syntax only
- Anti-patterns: `# BAD` / `# GOOD` pairs in the same code block
- Every skill should have at least one comparison or decision table
- No meta-commentary ("This skill covers…"), no filler prose

Read `skills/api-design/skill.md` and `skills/claude-api/skill.md` as canonical examples before writing a new one.

**After creating the skill file:**

1. Add an entry to the skill inventory table in `CLAUDE.md`
2. Add an entry to the skill inventory table in `README.md`
3. Run `make lint` to catch any markdown issues

---

## Adding an agent

Agents live at `.claude/agents/<name>.md`:

```markdown
---
name: kebab-case-name
description: One sentence — when to delegate to this agent vs. a slash command.
tools: Read, Grep, Glob, Bash   # minimum required; omit to inherit all
model: sonnet                   # sonnet | opus | haiku | inherit
color: red                      # optional: red | blue | green | yellow | purple | orange
---

System prompt in second person ("You are a…").

Describe methodology, output format, and rules the agent must follow.
```

Agents run in an isolated context window. Restrict `tools` to the minimum needed — a read-only agent must not have `Write` or `Edit`.

After adding an agent, update the Agent Inventory table in `CLAUDE.md` and `README.md`.

---

## Adding a slash command

Slash commands live at `.claude/commands/<name>.md`. The file body is the prompt Claude receives when the command is invoked. Keep it focused: one task, clear output format.

---

## Running CI checks locally

```bash
make format   # run prettier over all skill markdown
make lint     # run markdownlint over all .md files
```

The full CI suite (skill format validation, cross-reference check, tool config validation) runs automatically on every push and PR to `main`. Check `.github/workflows/ci.yml` to see exactly what's validated.

---

## Pull request process

1. Fork the repo and push your branch
2. Open a PR — the template will prompt you for type of change, checklist, and testing notes
3. CI must pass before review
4. At least one approval is required to merge

Keep PRs focused: one skill per PR, or one logical fix. Bundled refactors should be discussed in an issue first.

---

## Code of conduct

Be direct and respectful. Feedback on contributions should be about the work, not the person. Skill quality matters — terse, accurate, and useful beats comprehensive and bloated.
