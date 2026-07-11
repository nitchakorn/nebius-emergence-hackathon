"""Static configuration for ClinicalxCRAFT."""
from pathlib import Path

# --- LLM (Nebius Token Factory — formerly "Nebius AI Studio") ---
# OpenAI-compatible endpoint; auth via NEBIUS_API_KEY env var. Confirmed against
# https://docs.tokenfactory.nebius.com/ai-models-inference/function-calling.
NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
# NVIDIA Nemotron 3 Super — 120B params (12B active, hybrid Mamba-2/MoE), up to 1M
# context, fine-tuned specifically for tool calling / long-horizon agentic workflows /
# structured outputs. Confirmed live on Nebius Token Factory (see the Nebius blog post
# announcing it). A much better fit for this 8-tool investigation loop than a small
# general-purpose model. If your account lacks quota for it, fall back to
# "meta-llama/Meta-Llama-3.1-8B-Instruct-fast" (smaller, faster, weaker at multi-step
# tool orchestration — confirmed working in Nebius's own function-calling docs example).
NEBIUS_MODEL = "nvidia/nemotron-3-super-120b-a12b"

# --- MCP server ---
# The "nebius" CRAFT cluster (distinct from the runtime.dev.emergence.ai cluster the other
# two apps in this repo use) — this is the one this hackathon account is provisioned on.
MCP_URL = "https://nebius.emergence.ai/mcp"
PROJECT_ID = "3b416ab1-0b78-4c2b-8c6a-1af246817ffe"
HEADERS = {"X-Project-ID": PROJECT_ID}

# --- Data connection ---
# TCGA Pan-Cancer Atlas, filtered to the tables relevant here. See prompts.DATASET_HINT for
# what's actually populated for the KIRC (kidney renal clear cell carcinoma) cohort this
# app targets.
CONNECTION_SLUG = "pancancer-atlas-1-3b416ab1"
DATABASE = "PANCANCER_ATLAS_1"
SCHEMA = "PANCANCER_ATLAS_FILTERED"
SCHEMA_NAME = "PANCANCER_ATLAS_FILTERED"
# 3-part schema catalog FQN (connection-slug.database.schema) — used ONLY for
# the generate_sql `schema` argument.
SCHEMA_FQN = "pancancer-atlas-1-3b416ab1.PANCANCER_ATLAS_1.PANCANCER_ATLAS_FILTERED"

# --- OAuth (static pre-registered client) ---
OAUTH_CLIENT_ID = "em-runtime-mcp"
OAUTH_METADATA_URL = (
    "https://runtime.prod.emergence.ai/keycloak/realms/hub/.well-known/openid-configuration"
)
OAUTH_CALLBACK_PORT = 9876
OAUTH_SCOPES = "openid profile email organization"
TOKEN_CACHE_PATH = Path(__file__).parent / ".token_cache.json"

# --- Demo default ---
# The cohort filter every query should apply: acronym = 'KIRC' in the clinical table,
# joined to the genomic tables via ParticipantBarcode = bcr_patient_barcode. KIRC (kidney
# renal clear cell carcinoma) — 518 patients, the deepest-covered cohort in the atlas
# across clinical/mutation/protein/purity data (verified live; see DATASET_HINT).
COHORT_ACRONYM = "KIRC"
COHORT_LABEL = "KIRC (kidney renal clear cell carcinoma)"
