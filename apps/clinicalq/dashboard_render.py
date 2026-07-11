"""Renders a dashboard_data.fetch_snapshot() dict as a self-contained HTML/CSS block,
in the same visual language as the user's hand-built cohort-snapshot artifacts —
but every number here comes from the live snapshot dict, nothing is hardcoded.

Meant to be embedded with st.components.v1.html(render_html(snapshot), ...).
"""
import html as _html

_CSS = """
.viz-root {
  --surface-1:      #fcfcfb;
  --page-plane:     #f9f9f7;
  --text-primary:   #0b0b0b;
  --text-secondary: #52514e;
  --text-muted:     #898781;
  --gridline:       #e1e0d9;
  --baseline:       #c3c2b7;
  --border:         rgba(11,11,11,0.10);
  --series-1:       #2a78d6;
  --series-1-wash:  rgba(42,120,214,0.10);
  --status-warning: #fab219;
  --status-warning-ink: #7a5200;
}
@media (prefers-color-scheme: dark) {
  .viz-root {
    --surface-1:      #1a1a19;
    --page-plane:     #0d0d0d;
    --text-primary:   #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted:     #898781;
    --gridline:       #2c2c2a;
    --baseline:       #383835;
    --border:         rgba(255,255,255,0.10);
    --series-1:       #3987e5;
    --series-1-wash:  rgba(57,135,229,0.14);
    --status-warning-ink: #ffd77a;
  }
}
.viz-root {
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  background: var(--page-plane);
  color: var(--text-primary);
  padding: 24px 20px 48px;
  max-width: 920px;
  margin: 0 auto;
  line-height: 1.5;
}
.viz-root * { box-sizing: border-box; }
.viz-root h1 { font-size: 22px; font-weight: 650; margin: 0 0 4px; letter-spacing: -0.01em; }
.viz-root .subtitle { color: var(--text-secondary); font-size: 14px; margin: 0 0 24px; }
.viz-root section { margin-bottom: 32px; }
.viz-root h2 {
  font-size: 13px; font-weight: 650; text-transform: uppercase; letter-spacing: 0.04em;
  color: var(--text-secondary); margin: 0 0 4px; padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}
.viz-root .card {
  background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 20px;
}
.viz-root .stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.viz-root .stat-tile {
  background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px;
}
.viz-root .stat-label { font-size: 12px; color: var(--text-secondary); margin-bottom: 6px; }
.viz-root .stat-value { font-size: 26px; font-weight: 650; letter-spacing: -0.01em; }
.viz-root .stat-sub { font-size: 12px; color: var(--text-muted); margin-top: 3px; }
.viz-root .bar-row { display: grid; grid-template-columns: 168px 1fr 70px; align-items: center; gap: 10px; padding: 5px 0; }
.viz-root .bar-label { font-size: 13px; color: var(--text-secondary); text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.viz-root .bar-track { position: relative; height: 20px; }
.viz-root .bar-baseline { position: absolute; left: 0; bottom: 0; width: 100%; height: 1px; background: var(--baseline); }
.viz-root .bar-fill { height: 20px; max-height: 20px; background: var(--series-1); border-radius: 4px 4px 0 0; }
.viz-root .bar-value { font-size: 13px; color: var(--text-primary); font-variant-numeric: tabular-nums; }
.viz-root .bar-value .pct { color: var(--text-muted); font-size: 11px; margin-left: 3px; }
.viz-root .cols-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.viz-root table { width: 100%; border-collapse: collapse; font-size: 13px; }
.viz-root th { text-align: left; font-weight: 600; color: var(--text-secondary); font-size: 11px; text-transform: uppercase; letter-spacing: 0.03em; padding: 0 10px 8px; border-bottom: 1px solid var(--gridline); }
.viz-root td { padding: 8px 10px; border-bottom: 1px solid var(--gridline); color: var(--text-primary); }
.viz-root tr:last-child td { border-bottom: none; }
.viz-root td.num, .viz-root th.num { text-align: right; font-variant-numeric: tabular-nums; }
.viz-root td.muted { color: var(--text-muted); }
.viz-root .callout {
  display: flex; gap: 10px; align-items: flex-start;
  background: color-mix(in srgb, var(--status-warning) 12%, var(--surface-1));
  border: 1px solid color-mix(in srgb, var(--status-warning) 35%, var(--border));
  border-radius: 8px; padding: 12px 14px; font-size: 13px; color: var(--text-primary); margin-top: 14px;
}
.viz-root .callout.plain { background: transparent; border: none; padding: 12px 0 0; margin-top: 8px; }
.viz-root .callout .icon { color: var(--status-warning-ink); font-weight: 700; flex-shrink: 0; }
.viz-root footer { font-size: 12px; color: var(--text-muted); border-top: 1px solid var(--border); padding-top: 14px; margin-top: 4px; }
"""


def _esc(v) -> str:
    return _html.escape(str(v))


def _bar_chart(pairs: list, limit: int = 8) -> str:
    if not pairs:
        return '<p style="color:var(--text-muted);font-size:13px;">No data.</p>'
    pairs = pairs[:limit]
    top = max(v for _, v in pairs) or 1
    rows = []
    for label, value in pairs:
        width = round(value / top * 100, 1)
        rows.append(
            f'<div class="bar-row"><div class="bar-label">{_esc(label)}</div>'
            f'<div class="bar-track"><div class="bar-baseline"></div>'
            f'<div class="bar-fill" style="width:{width}%"></div></div>'
            f'<div class="bar-value">{int(value)}</div></div>'
        )
    return "".join(rows)


def _table(pairs: list, total: float | None, limit: int = 6) -> str:
    if not pairs:
        return '<p style="color:var(--text-muted);font-size:13px;">No data.</p>'
    rows = []
    for label, value in pairs[:limit]:
        pct = f'<td class="num muted">{value / total * 100:.0f}%</td>' if total else ""
        rows.append(f'<tr><td>{_esc(label)}</td><td class="num">{int(value)}</td>{pct}</tr>')
    return f"<table>{''.join(rows)}</table>"


def _section_body(sections: dict, key: str, label: str, render_fn) -> str:
    data = sections.get(key)
    if not data or data.get("error"):
        msg = data.get("error", "no data") if data else "no data"
        return (
            '<div class="callout"><span class="icon">&#9888;</span>'
            f'<span>Couldn\'t fetch <strong>{_esc(label)}</strong>: {_esc(msg)}</span></div>'
        )
    return render_fn(data)


def render_html(snapshot: dict) -> str:
    sections = snapshot.get("sections", {})
    total = snapshot.get("total_patients")
    pancancer_total = snapshot.get("pancancer_total")
    fetched_at = snapshot.get("fetched_at", "")

    subtitle = f"{int(total) if total else '?'} KIRC patients"
    if pancancer_total:
        subtitle += f" of {int(pancancer_total)} pan-cancer total"
    subtitle += " · TCGA Pan-Cancer Atlas, live via Craft / Snowflake"

    # --- stat tiles ---
    vs_pairs = sections.get("vital_status", {}).get("pairs") or []
    vs_lookup = {label.lower(): v for label, v in vs_pairs}
    dead = next((v for k, v in vs_lookup.items() if "dead" in k or "deceased" in k), None)
    alive = next((v for k, v in vs_lookup.items() if "alive" in k), None)

    age = sections.get("age", {})
    sex_pairs = sections.get("sex", {}).get("pairs") or []

    tiles = [
        ("Patients", f"{int(total)}" if total else "—", f"of {int(pancancer_total)} pan-cancer total" if pancancer_total else ""),
        (
            "Vital status",
            f"{int(dead)} dead" if dead is not None else "—",
            f"{dead / total * 100:.0f}% · {int(alive)} alive" if dead is not None and alive is not None and total else "",
        ),
        (
            "Age at diagnosis",
            f"{age['avg']:.1f} avg" if age.get("avg") is not None else "—",
            f"range {age['min']:.0f}–{age['max']:.0f}" if age.get("min") is not None else "",
        ),
        (
            "Sex",
            f"{sex_pairs[0][1] / total * 100:.0f}% {sex_pairs[0][0]}" if sex_pairs and total else "—",
            ", ".join(f"{int(v)} {l}" for l, v in sex_pairs[:2]),
        ),
    ]
    stat_html = "".join(
        f'<div class="stat-tile"><div class="stat-label">{_esc(l)}</div>'
        f'<div class="stat-value">{_esc(v)}</div><div class="stat-sub">{_esc(s)}</div></div>'
        for l, v, s in tiles
    )

    # --- resection-bias callout, numbers pulled from live data ---
    top_surgery = (sections.get("surgery", {}).get("pairs") or [(None, None)])[0]
    top_stage = (sections.get("stage", {}).get("pairs") or [(None, None)])[0]
    bias_note = ""
    if top_surgery[0] and top_stage[0] and total:
        bias_note = (
            '<div class="callout"><span class="icon">&#9888;</span>'
            "<span><strong>Resection bias:</strong> TCGA required surgical tissue, so this "
            f"cohort skews toward resectable, surgically-treated disease ({top_surgery[1] / total * 100:.0f}% "
            f"{_esc(top_surgery[0])}, {top_stage[1] / total * 100:.0f}% {_esc(top_stage[0])}) — it "
            "under-represents unresectable/metastatic presentations common in real-world diagnoses."
            "</span></div>"
        )

    # --- genomic drivers callout ---
    genes = sections.get("genes", {}).get("pairs") or []
    genes_note = ""
    if genes:
        top_gene = genes[0][0]
        coverage = sections.get("mutation_coverage", {}).get("n")
        cov_txt = f" ({int(coverage)}/{int(total)} patients with mutation data)" if coverage and total else ""
        genes_note = (
            '<div class="callout plain"><span class="icon" style="color:var(--text-muted);">&#9432;</span>'
            f"<span style=\"color:var(--text-secondary);\">Most frequently mutated: <strong>{_esc(top_gene)}</strong>"
            f"{cov_txt}. Genes mutated in only 1-2 samples are more likely noise than drivers at this "
            "sample size — treat the tail of this list as illustrative.</span></div>"
        )

    return f"""<div class="viz-root"><style>{_CSS}</style>
  <h1>Kidney Renal Clear Cell Carcinoma (KIRC) — Cohort Snapshot</h1>
  <p class="subtitle">{_esc(subtitle)}</p>

  <section>
    <h2>Cohort at a glance</h2>
    <div class="stat-grid">{stat_html}</div>
    {bias_note}
  </section>

  <section>
    <h2>Clinical profile</h2>
    <div class="cols-2">
      <div class="card">
        <div style="font-size:13px;font-weight:600;margin-bottom:12px;">Pathologic stage</div>
        <div>{_section_body(sections, "stage", "pathologic stage", lambda d: _bar_chart(d.get("pairs")))}</div>
      </div>
      <div class="card">
        <div style="font-size:13px;font-weight:600;margin-bottom:12px;">Surgery performed</div>
        <div>{_section_body(sections, "surgery", "surgery performed", lambda d: _bar_chart(d.get("pairs")))}</div>
      </div>
    </div>
    <div class="cols-2" style="margin-top:16px;">
      <div class="card">
        <div style="font-size:13px;font-weight:600;margin-bottom:12px;">Histological type</div>
        {_section_body(sections, "histology", "histological type", lambda d: _table(d.get("pairs"), total))}
      </div>
      <div class="card">
        <div style="font-size:13px;font-weight:600;margin-bottom:12px;">Race</div>
        {_section_body(sections, "race", "race", lambda d: _table(d.get("pairs"), total))}
      </div>
    </div>
  </section>

  <section>
    <h2>Genomic drivers <span style="color:var(--text-muted);font-weight:500;text-transform:none;">— MC3 somatic mutations</span></h2>
    <p style="font-size:13px;color:var(--text-secondary);margin:10px 0 16px;">Distinct patients carrying &ge;1 mutation in each gene, as a share of the full cohort.</p>
    <div class="card">
      {_section_body(sections, "genes", "top mutated genes", lambda d: _bar_chart(d.get("pairs"), limit=10))}
      {genes_note}
    </div>
  </section>

  <footer>
    <p>Source: TCGA Pan-Cancer Atlas, live via Craft → Snowflake connection <code>pancancer-atlas-1</code>. Snapshot fetched {_esc(fetched_at)}. Filtered to acronym = 'KIRC'; each figure is a direct query, not a cached/hardcoded number.</p>
  </footer>
</div>"""
