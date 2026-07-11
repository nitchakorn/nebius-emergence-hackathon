"""Deterministic cohort-snapshot data for the dashboard UI (app_dashboard.py).

Unlike agent.py's free-form investigation, this runs a fixed, known set of questions
through CraftClient.ask() — no agentic tool-use loop, no schema rediscovery. It exists
purely to populate the dashboard fast and predictably; open-ended investigation still goes
through agent.run() (see app_dashboard.py's follow-up box).
"""
import json
import os
from datetime import datetime, timezone
from typing import Callable

from .craft_client import CraftClient, QueryResult
from .tools import _with_retry

SNAPSHOT_PATH = os.path.join(os.path.dirname(__file__), "runs", "dashboard_snapshot.json")

# (section key, human label for progress callback, question) — each resolves to a
# label/count breakdown via _label_count_pairs.
GROUP_SECTIONS = [
    ("vital_status", "vital status", "For the KIRC cohort (acronym = 'KIRC' in the clinical table), return the count of patients grouped by vital_status."),
    ("sex", "sex", "For the KIRC cohort, return the count of patients grouped by gender."),
    ("stage", "pathologic stage", "For the KIRC cohort, return the count of patients grouped by pathologic_stage, ordered by count descending."),
    ("surgery", "surgery performed", "For the KIRC cohort, return the count of patients grouped by surgery_performed_type, ordered by count descending."),
    ("histology", "histological type", "For the KIRC cohort, return the count of patients grouped by histological_type, ordered by count descending."),
    ("race", "race", "For the KIRC cohort, return the count of patients grouped by race, ordered by count descending."),
    ("genes", "top mutated genes", "Using the MC3 somatic mutation table (MC3_MAF_V5_ONE_PER_TUMOR_SAMPLE) joined to the KIRC clinical cohort via ParticipantBarcode = bcr_patient_barcode, return the top 10 genes (Hugo_Symbol) by count of distinct patients with at least one mutation in that gene, ordered by count descending."),
]

AGE_QUESTION = (
    "For the KIRC cohort, return the average, minimum, and maximum "
    "age_at_initial_pathologic_diagnosis."
)
MUTATION_COVERAGE_QUESTION = (
    "Using the MC3 somatic mutation table joined to the KIRC clinical cohort via "
    "ParticipantBarcode = bcr_patient_barcode, return the count of distinct patients "
    "with at least one recorded mutation."
)
PANCANCER_TOTAL_QUESTION = (
    "Return the total distinct count of patients across all cancer types in the "
    "clinical table, not filtered to any one cancer type."
)


def _numeric(val) -> float | None:
    try:
        return float(str(val).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _label_count_pairs(qr: QueryResult) -> list[tuple[str, float]]:
    """Best-effort (label, count) extraction from a 'group by X, count' result whose
    exact column names/order are chosen by CRAFT's NL2SQL, not us."""
    if not qr.rows or not qr.columns:
        return []
    ncols = len(qr.columns)
    numeric_idx = next(
        (i for i, name in enumerate(qr.columns) if "count" in (name or "").lower()), None
    )
    if numeric_idx is None:
        numeric_idx = next(
            (
                i
                for i in range(ncols - 1, -1, -1)
                if all(_numeric(r[i]) is not None for r in qr.rows if i < len(r))
            ),
            ncols - 1,
        )
    label_idx = next((i for i in range(ncols) if i != numeric_idx), 0)
    pairs = []
    for r in qr.rows:
        if len(r) <= max(numeric_idx, label_idx):
            continue
        val = _numeric(r[numeric_idx])
        if val is None:
            continue
        label = str(r[label_idx]).strip() or "Not recorded"
        pairs.append((label, val))
    pairs.sort(key=lambda p: p[1], reverse=True)
    return pairs


def _pick(d: dict, keyword: str):
    for k, v in d.items():
        if keyword in k.lower():
            return v
    return None


def _single_number(qr: QueryResult) -> float | None:
    if not qr.dicts:
        return None
    row = qr.dicts[0]
    for v in row.values():
        n = _numeric(v)
        if n is not None:
            return n
    return None


async def _ask(client: CraftClient, question: str) -> QueryResult:
    async def call():
        return await client.ask(question)

    return await _with_retry(call)


async def fetch_snapshot(on_progress: Callable[[str], None] | None = None) -> dict:
    """Fetch a fresh cohort snapshot via a fixed set of direct CRAFT queries.

    Opens its own CraftClient session (same pattern as agent.run). A failing section is
    stored as {"error": "..."} rather than raising, so one bad query doesn't take down the
    whole dashboard.
    """
    def progress(label: str) -> None:
        if on_progress:
            on_progress(label)

    sections: dict = {}
    async with CraftClient() as client:
        for key, label, question in GROUP_SECTIONS:
            progress(f"Fetching {label}…")
            try:
                qr = await _ask(client, question)
                sections[key] = {"pairs": _label_count_pairs(qr), "sql": qr.sql}
            except Exception as e:
                sections[key] = {"error": str(e)}

        progress("Fetching age at diagnosis…")
        try:
            qr = await _ask(client, AGE_QUESTION)
            row = qr.dicts[0] if qr.dicts else {}
            sections["age"] = {
                "avg": _numeric(_pick(row, "avg")),
                "min": _numeric(_pick(row, "min")),
                "max": _numeric(_pick(row, "max")),
            }
        except Exception as e:
            sections["age"] = {"error": str(e)}

        progress("Fetching mutation data coverage…")
        try:
            qr = await _ask(client, MUTATION_COVERAGE_QUESTION)
            sections["mutation_coverage"] = {"n": _single_number(qr)}
        except Exception as e:
            sections["mutation_coverage"] = {"error": str(e)}

        pancancer_total = None
        progress("Fetching pan-cancer total…")
        try:
            qr = await _ask(client, PANCANCER_TOTAL_QUESTION)
            pancancer_total = _single_number(qr)
        except Exception:
            pass  # purely decorative context — fine to omit on failure

    total_patients = None
    vs = sections.get("vital_status", {})
    if vs.get("pairs"):
        total_patients = sum(v for _, v in vs["pairs"])

    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "total_patients": total_patients,
        "pancancer_total": pancancer_total,
        "sections": sections,
    }


def save_snapshot(snapshot: dict) -> str:
    os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
    with open(SNAPSHOT_PATH, "w") as f:
        json.dump(snapshot, f, indent=2)
    return SNAPSHOT_PATH


def load_cached_snapshot() -> dict | None:
    if not os.path.exists(SNAPSHOT_PATH):
        return None
    try:
        with open(SNAPSHOT_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _fmt_pairs(pairs: list, total: float | None, limit: int = 6) -> str:
    parts = []
    for label, count in pairs[:limit]:
        pct = f" ({count / total * 100:.0f}%)" if total else ""
        parts.append(f"{label} {int(count)}{pct}")
    return ", ".join(parts)


def summarize_for_context(snapshot: dict) -> str:
    """Compact plain-text digest of the snapshot, threaded into follow-up questions as
    context (see prompts.user_message) — not the HTML, just the numbers."""
    total = snapshot.get("total_patients")
    sections = snapshot.get("sections", {})
    lines = []

    header = f"{int(total)} KIRC patients" if total else "KIRC cohort"
    pancancer = snapshot.get("pancancer_total")
    if pancancer:
        header += f" (of {int(pancancer)} pan-cancer total)"
    lines.append(header + ".")

    age = sections.get("age", {})
    if age.get("avg") is not None:
        lines.append(
            f"Age at diagnosis: avg {age['avg']:.1f}"
            + (f", range {age['min']:.0f}–{age['max']:.0f}" if age.get("min") is not None else "")
            + "."
        )

    labels = {
        "vital_status": "Vital status",
        "sex": "Sex",
        "stage": "Pathologic stage",
        "surgery": "Surgery performed",
        "histology": "Histological type",
        "race": "Race",
    }
    for key, label in labels.items():
        pairs = sections.get(key, {}).get("pairs")
        if pairs:
            lines.append(f"{label}: {_fmt_pairs(pairs, total)}.")

    genes = sections.get("genes", {}).get("pairs")
    if genes:
        coverage = sections.get("mutation_coverage", {}).get("n")
        cov_note = f" ({int(coverage)}/{int(total)} patients have mutation data)" if coverage and total else ""
        lines.append(f"Top mutated genes{cov_note}: {_fmt_pairs(genes, total, limit=8)}.")

    return " ".join(lines)
