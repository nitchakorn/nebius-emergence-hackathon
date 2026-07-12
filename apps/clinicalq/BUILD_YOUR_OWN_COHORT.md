# Build ClinicalxCRAFT for your own cancer type

ClinicalxCRAFT was built for KIRC (kidney cancer), but nothing about it is
kidney-specific — the app just filters the same TCGA Pan-Cancer Atlas connection to one
`acronym`. This guide is for any clinician who wants their own version, for their own
cancer type, using **Claude Code** (this tool) paired with **CRAFT** (the MCP server that
does the actual data querying). You do not need to write SQL or Python yourself — you
describe what you want, Claude Code does the schema discovery and the coding, and you
review what it finds.

---

## Before you start

- **Claude Code**, with the CRAFT MCP server connected (the same connection this repo's
  `craft_client.py` / `craft_auth.py` use — ask whoever gave you hackathon/CRAFT access for
  the connection details if you don't already have them).
- **A Nebius Token Factory API key** (`NEBIUS_API_KEY`) — the deployed app's reasoning
  model runs on Nebius, separately from Claude Code itself. Free to get at
  [tokenfactory.nebius.com](https://tokenfactory.nebius.com/).
- **A clone of this repo.**
- **Your cancer type's TCGA study abbreviation** — a 4-5 letter code, e.g. `BRCA` (breast),
  `LUAD` (lung adenocarcinoma), `COAD` (colon), `SKCM` (melanoma), `PAAD` (pancreatic — the
  original build). If you don't know yours, ask Claude Code to look up the TCGA Pan-Cancer
  Atlas study abbreviation list — it's one of the first things the prompt below has it do
  anyway.

---

## The prompt

Copy this into Claude Code, with `{CANCER_TYPE}` replaced by your cancer (plain English is
fine — "ovarian cancer," "melanoma," whatever you'd say to a colleague). Do this from
inside the repo, so Claude Code can see the existing KIRC build as a working reference.

```
I want to adapt this ClinicalxCRAFT app (currently built for KIRC, kidney cancer) to
{CANCER_TYPE} instead. Use apps/clinicalq/ as the reference implementation — same
architecture, same two-Streamlit-app structure, same specimen-ledger pattern — but
re-derive every number and every table-coverage claim from scratch for this new cohort.
Do not assume anything from the KIRC version carries over except the code structure.

Specifically:

1. Find the correct TCGA study acronym for {CANCER_TYPE} and confirm the patient count
   in the clinical table (CLINICAL_PANCAN_PATIENT_WITH_FOLLOWUP_FILTERED, filtered to
   that acronym) by an actual query, not a guess.

2. Look up (web search is fine) the significantly-mutated driver genes published for this
   cancer type in the TCGA literature — the genes a clinician would expect to see.

3. For each of those genes, and for this cohort specifically, directly query real
   coverage in: the mutation table (MC3_MAF_V5_ONE_PER_TUMOR_SAMPLE), the protein table
   (TCGA_RPPA_PANCAN_CLEAN_FILTERED), the purity/ploidy table
   (PURITY_PLOIDY_ALL_SAMPLES_FILTERED), the copy-number table
   (ALL_CNVR_DATA_BY_GENE_FILTERED), and the RNA-seq table
   (EBPP_ADJUSTPANCAN_ILLUMINAHISEQ_RNASEQV2_GENEXP_FILTERED). Report real numbers (N of
   total cohort) for each — don't assume a table is usable just because it exists; some
   of these are sparse for specific genes even when the table itself looks populated.
   Tell me plainly which tables are actually worth building on for this cancer type and
   which aren't, and why.

4. Check whether the IDC (Imaging Data Commons) connection has a matching collection for
   this cancer type (collection IDs are usually "tcga_" + the lowercase acronym) and how
   many patients/studies it covers.

5. Once you know what's actually there, update: config.py (COHORT_ACRONYM,
   COHORT_LABEL), prompts.py's DATASET_HINT (with the real coverage numbers from step 3,
   not placeholder text), dashboard_data.py and dashboard_render.py (swap the cohort-
   specific query filters and labels), and build a new specimen ledger — a
   self-contained HTML page like kirc_ledger.html, listing each patient with their
   demographics, mutation status for the genes that actually check out, protein/purity
   values where covered, and a link to their imaging series in IDC's viewer where
   available. Default the ledger's view to patients who have imaging, since that's the
   most complete/interesting record per patient, but don't hide or drop patients without
   it.

6. Compile-check everything, and tell me honestly if any of the six driver genes turned
   out to have too little data to build a real finding on — I'd rather know that upfront
   than have the deployed app hallucinate a pattern from three patients.

Ask me before renaming the product or touching anything outside apps/clinicalq/.
```

---

## What to expect while it works

Claude Code will spend real time on steps 1–4 — that's query time against CRAFT, not
wasted time. The KIRC build's coverage numbers (518 patients; mutations well-covered;
protein 451/518; purity/ploidy 330/518; copy-number and RNA-seq essentially unusable for
the six driver genes specifically) only exist because each was checked with a real count,
not assumed. Some cancer types will have richer imaging coverage and thinner genomic
coverage, or vice versa — that's expected, and the resulting app should say so honestly
rather than paper over it.

If a gene or table comes back too sparse to use, that's not a failure — it's exactly the
kind of thing worth knowing *before* building a feature on top of it, and the app's system
prompt should say so explicitly so the investigating model doesn't build a false finding on
thin data later.

---

## After it's built

- **Run it locally first:** `streamlit run apps/clinicalq/app_dashboard.py` with
  `NEBIUS_API_KEY` set and CRAFT OAuth completed once (opens a browser tab).
- **Sanity-check a few patients by hand** against the ledger before trusting it — pick two
  or three barcodes you can also see in the raw CRAFT data and confirm they match.
- **If you want a public link** (e.g. to show a colleague), Streamlit Community Cloud
  works, but know the tradeoff: the CRAFT login this app uses is tied to *your* personal
  session and the tokens are short-lived (well under an hour), so a hosted deployment needs
  its secret refreshed shortly before anyone actually looks at it — it isn't a
  deploy-once-forget-it setup with this kind of credential. Fine for showing someone during
  a call; not yet a stable always-on tool.

---

## The one rule underneath all of this

Every number this app has ever shown came from a real query against real data — never a
plausible-sounding guess. That's the whole point of building this on CRAFT instead of
hand-writing SQL, and it's worth holding your own cohort's build to the same standard:
if Claude Code tells you a table is "well covered," ask it to show you the actual count.
