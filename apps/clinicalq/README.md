# ClinicalxCRAFT (Kidney Cancer Cohort Investigator)

Ask a free-text question about the KIRC (kidney renal clear cell carcinoma) cohort in the
TCGA Pan-Cancer Atlas and the model investigates it like a clinical research analyst: forms
a hypothesis, tests it with real queries against both the clinical and genomic tables,
follows the evidence, and reports back. Every number comes from the data itself, pulled
**entirely through the CRAFT MCP server** — there is no hand-written SQL anywhere in the
codebase. KIRC was chosen deliberately: it's the deepest-covered cohort in the whole
atlas — 518 patients, well-populated mutation, protein, and purity/ploidy tables, all
tracing the same VHL→HIF→mTOR biology.

**The agent is LLM-orchestrated**, following the same architecture as this repo's
[Seller Delivery Intelligence Agent](../seller_delivery_agent/) — but the LLM here is a
model hosted on **Nebius Token Factory** (OpenAI-compatible API), not Claude directly. The
model is given the raw MCP tools and a goal; *it* decides which schema to explore, which
questions to ask, when to run each query, when to chart, and when it has enough to write
the report.

**Want this for a different cancer type?** Nothing here is kidney-specific — see
[`BUILD_YOUR_OWN_COHORT.md`](./BUILD_YOUR_OWN_COHORT.md) for a copy-paste Claude Code
prompt that re-derives the whole thing (coverage numbers, driver genes, specimen ledger)
for any TCGA cohort.

---

## What it does

Given a free-text question, the model runs an **agentic tool-use loop** over nine tools,
each backed by an authenticated CRAFT MCP session against the Pan-Cancer Atlas (plus one
that isn't CRAFT at all):

- `web_search(query)` — Wikipedia-backed background search for gene function/disease
  mechanism, used for grounding, not as a substitute for the cohort's own data. Always
  cited (title + URL) when used, in the model's notes and in the final report.
- `note(thought)` — narrate its current hypothesis/reasoning live, before each step
- `search_schema(query)` — find tables/columns by keyword
- `get_schema(fqn)` — read a table's columns, types, and business definitions
- `sample_data(table_fqn)` — peek at real rows to understand values and formats
- `generate_sql(question)` — describe an analytical question in words → schema-bound SQL
- `execute_query(sql)` → an artifact handle
- `get_result_page(artifact_fqn)` → the rows
- `generate_plotly_chart(chart_type, data, options)` → a saved PNG

No schema is handed to the model up front — it discovers KIRC-relevant tables itself, but
the system prompt (`prompts.py`) does flag non-obvious gotchas so the model doesn't burn
turns rediscovering them: the clinical table is a 746-column pan-cancer union schema where
most columns are null for KIRC; the copy-number and RNA-seq tables *look* populated but are
essentially unusable for KIRC's own driver genes (verified live: ~1 patient per gene for
copy-number, 27/518 for VHL expression) — the model is told this up front rather than
discovering it the hard way. In `app_dashboard.py`, the model is also told to treat the
cohort snapshot table already shown on screen as a known baseline and build on it rather
than re-deriving those numbers from scratch.

---

## Prerequisites

- **Python 3.11+**
- **A Keycloak / SSO account** provisioned for the `nebius.emergence.ai` CRAFT cluster
  (this is a *different* cluster/project than `seller_delivery_agent` and
  `customer-experience-agent` use — see `config.py`). First run opens a browser for OAuth
  (once).
- **A Nebius Token Factory API key** (`NEBIUS_API_KEY`) — get one at
  [tokenfactory.nebius.com](https://tokenfactory.nebius.com/). This is a *different*
  credential from the CRAFT/Keycloak login above.

## Setup

```bash
# from the repository root
python3 -m venv .venv
.venv/bin/pip install -r apps/clinicalq/requirements.txt
```

## Run

```bash
export NEBIUS_API_KEY=...
```

then:

### Web UI (recommended for a demo)

```bash
.venv/bin/streamlit run apps/clinicalq/app.py
```

1. Click **Check connection** — completes Keycloak OAuth on first run and verifies the
   MCP server responds (`hello_world`).
2. Type your own question, or pick one of the example questions in the sidebar.
3. Click **🔎 Investigate** — watch the live reasoning trace, then the report renders on
   the left, any charts on the right, and the model's notes + generated SQL in expanders
   below.

### Web UI, dashboard version

```bash
.venv/bin/streamlit run apps/clinicalq/app_dashboard.py
```

A second, independent entrypoint (`app.py` above still works unchanged) for a
"see the data, then ask" flow instead of a blank question box:

1. On first load it fetches a **cohort snapshot** — patient count, vital status, age,
   sex, stage, surgery, histology, race, and top mutated genes — via a fixed set of
   direct CRAFT queries (`dashboard_data.py`, no agentic loop, so it's fast and
   deterministic). Cached to `runs/dashboard_snapshot.json`; **Refresh** re-fetches.
2. Click one of the **"Ask about this"** buttons (scoped to a dashboard section) or type
   your own follow-up, then **🔎 Investigate**. This runs the same `agent.run()` loop as
   `app.py`, but the model is given the visible snapshot as context so it treats those
   numbers as known baseline and goes straight to deeper investigation instead of
   re-deriving them.

### CLI

```bash
.venv/bin/python -m apps.clinicalq.agent ["<question>"]
```

Defaults to: *"In this KIRC (kidney cancer) cohort, do patients with a VHL mutation differ
in outcome or PI3K/AKT/mTOR protein signaling from those without one?"*

Both entrypoints share the exact same `agent.run()` pipeline; the UI is a thin wrapper.

---

## Outputs

Each run writes to `apps/clinicalq/runs/investigation_{timestamp}/`:

| File | Description |
| --- | --- |
| `report.md` | The final report (Answer, Evidence, Clinical interpretation, Caveats) |
| `reasoning_trace.md` | The model's own `note()` narration, in order |
| `chart_1.png`, `chart_2.png`, … | The charts the model chose to build |
| `sql_queries.txt` | Every query the model generated (audit trail — none hand-written) |
| `raw_data.json` | The result rows the model collected, tagged by the question that produced them |

---

## How it connects (auth)

Two separate credentials, two separate services:

- **Data (CRAFT MCP):** the agent is a standalone MCP client (`mcp` Python SDK) that talks
  to `https://nebius.emergence.ai/mcp` over streamable HTTP, authenticating via Keycloak
  OAuth (`OAuthClientProvider`, static client `em-runtime-mcp`, callback port 9876). The
  token is cached to `apps/clinicalq/.token_cache.json` (gitignored) and reused on later
  runs; expiry re-opens the browser automatically. Every request carries the required
  `X-Project-ID` header (`3b416ab1-0b78-4c2b-8c6a-1af246817ffe`).
- **LLM (Nebius Token Factory):** `llm.py` talks to `config.NEBIUS_BASE_URL`
  (`https://api.tokenfactory.nebius.com/v1/`) via the OpenAI Python SDK, authenticating
  with the `NEBIUS_API_KEY` env var. No token caching — just the env var, every run.

---

## Troubleshooting

- **`RuntimeError: NEBIUS_API_KEY is not set`**: `export NEBIUS_API_KEY=...` before
  running — get a key from [tokenfactory.nebius.com](https://tokenfactory.nebius.com/).
- **401/403 from the LLM call**: bad or expired `NEBIUS_API_KEY`, or your account doesn't
  have quota for `config.NEBIUS_MODEL` — check your Nebius dashboard.
- **Port 9876 already in use** (CRAFT OAuth callback): `lsof -ti:9876 | xargs kill`, then
  retry. Or change `OAUTH_CALLBACK_PORT` in `config.py`.
- **`401 Unauthorized` / corrupted token from CRAFT**: `rm -f apps/clinicalq/.token_cache.json`
  and re-run — the OAuth flow restarts.
- **Browser didn't open** (CRAFT OAuth): copy the URL printed in the terminal and open it
  manually.
- **`403 Forbidden` / empty results from CRAFT**: your account may not be provisioned on
  the `nebius.emergence.ai` cluster/project — check with your host.
- **No quota / rate-limited on `nvidia/nemotron-3-super-120b-a12b`**: the default model is
  120B params — check your Nebius plan's quota for it. If unavailable, fall back to the
  smaller `meta-llama/Meta-Llama-3.1-8B-Instruct-fast` in `config.py` (faster and always
  available per Nebius's own docs, but noticeably weaker at multi-step tool orchestration
  — expect a less coherent investigation).
- **Slow first response**: Nemotron 3 Super's time-to-first-token is ~10-15s on Nebius per
  published benchmarks — normal for a 120B model, not a hang. Each subsequent tool-call
  turn adds more.

---

## Project layout

```
apps/clinicalq/
  app.py               # Streamlit UI, free-text version (thin wrapper over agent.run)
  app_dashboard.py     # Streamlit UI, dashboard + contextual follow-up version
  dashboard_data.py    # fixed direct CRAFT queries that populate the dashboard snapshot
  dashboard_render.py  # renders a snapshot dict as HTML for app_dashboard.py
  agent.py             # orchestration (drives the LLM loop) + CLI + progress callback
  llm.py               # Nebius (OpenAI-compatible) client factory + the agentic tool-use loop
  tools.py             # OpenAI-format tool defs + ToolExecutor (bridges tool calls -> MCP session)
  prompts.py           # system prompt (goal + KIRC dataset hint + 4-section output spec)
  craft_client.py      # MCP session + response parsers (backs the tools)
  craft_auth.py        # OAuth (FileTokenStorage + OAuthClientProvider)
  charts.py            # render a Plotly figure spec -> PNG
  config.py            # connection slug, project id, OAuth settings
  runs/                # per-run output + dashboard_snapshot.json cache (gitignored)
```
