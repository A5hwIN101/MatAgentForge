# MatAgent-Forge: AI-Powered Materials Science Discovery Platform

MatAgent-Forge is a physics-aware materials analysis platform that combines:

- a **Next.js** UI,
- a **FastAPI** backend,
- a **LangGraph** state-machine pipeline, and
- a **paper-derived quantitative rule engine** (arXiv/PMC → JSON rules → analysis).

It is designed to accelerate materials exploration by turning database properties + literature rules into a single, readable, evidence-backed markdown report.

## 📋 Development Progress

### Completed Phases

#### Rule Extraction & Integration (Phase 1a - 1.5b)
- ✅ **Phase 1a**: Paper Scraper - Extract rules from arXiv/PMC papers
- ✅ **Phase 1a+**: Rule Quality Improvement - Quantitative, domain-aware rules with statistical confidence
- ✅ **Phase 1a++**: Standardized Rule Schema - Complete schema with all fields (edge_cases, fails_for, validation_status, etc.)
- ✅ **Phase 1.5**: Rules integrated into Analysis Agent for known materials (Materials Project hits)
- ✅ **Phase 1.5b**: Simulation Agent rule-integration implemented (experimental module; not yet routed by LangGraph pipeline)

#### LangGraph State Machine Architecture (Phase 1.5c)
- ✅ **Explicit State Management**: `PipelineState` TypedDict as single source of truth
- ✅ **6-Node `StateGraph`**: `lookup → validate_chemistry → analyze → hypothesize → format → error`
- ✅ **Conditional Edge Routing**: Validation/analysis failures route to `error`
- ✅ **Async Pipeline**: Nodes are `async` for non-blocking execution
- ✅ **Backend Integration**: FastAPI endpoint streams markdown (`POST /api/analyze`)
- ✅ **Test Suite Included**: `src/orchestrator/tests/test_pipeline.py` covers state, routing, nodes, and graph execution

**Architecture Highlights (current LangGraph pipeline):**

```text
Input (formula)
  ↓
lookup_node                → Materials Project lookup (mp-api)
  ↓
validate_chemistry_node    → Guardrails on retrieved properties
  ├─ passed  → analyze_node      → heuristic analysis + rule matching
  │            ↓
  │          hypothesize_node   → deterministic hypotheses from properties
  │            ↓
  │          format_node        → markdown report
  │            ↓
  └────────────────────────────→ END (success)

  └─ failed  → error_node        → markdown error report
               ↓
             END (error)
```

### Current Status (verified from `rules/` + code)
- ✅ **Rules extracted**: 24 total; 21/24 high confidence (≥ 0.8) = 87.5%
- ✅ **Rule metadata stored**: confidence, uncertainty, evidence strength, validation status, etc.
- ✅ **Rule validation**: rejects confidence < 0.6; flags uncertainty > 0.3 (warning)
- ✅ **LangGraph pipeline wired to API**: `POST /api/analyze` returns a streaming markdown response

**Domains covered (from stored rule data):** photovoltaics, thermoelectric, battery, structural, optoelectronics, general

### Next Phases
- 🔄 **Phase 2**: OQMD Integration - add fallback data source + expand rule database
- 🔄 **Phase 3**: ICSD Integration - experimental structure data integration
- 🔄 **Phase 4**: Production Hardening - tracing, checkpointing, reliability & compliance review

---

## 🔧 Setup

### Prerequisites
- **Python 3.10+**
- **Node.js 18+** (npm)
- **Materials Project API Key** ([Get one here](https://next-gen.materialsproject.org/api))
- **Groq API Key** ([Get one here](https://console.groq.com/))

### Environment Variables

Create a `.env` file in the repository root:

```env
MP_API_KEY=your_materials_project_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

### Backend Installation (Python)

1. Create and activate a virtual environment:

```bash
python -m venv venv
```

Windows (PowerShell):

```powershell
venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Install runtime packages used by the API/pipeline (currently imported by code, but not listed in `requirements.txt` yet):

```bash
pip install fastapi "uvicorn[standard]" langgraph typing_extensions
```

4. Optional (only if you run the Simulation Agent module):

```bash
pip install m3gnet
```

### Frontend Installation (Next.js)

```bash
npm install
```

If deploying the frontend separately, update the backend URL in `components/gemini-adapter.tsx`:

```typescript
const BACKEND_URL = "http://localhost:8000";
```

---

## 🛠️ Usage

### Run the Full Stack (recommended)

1. Start the FastAPI backend:

```bash
uvicorn src.orchestrator.main:app --reload --port 8000
```

2. Start the Next.js frontend (separate terminal):

```bash
npm run dev
```

3. Open:
- **Frontend**: `http://localhost:3000`
- **Backend health**: `http://localhost:8000/health`

### API Endpoints

#### Analyze Material (streaming markdown)

macOS/Linux:

```bash
curl -N -X POST "http://localhost:8000/api/analyze" \
  -H "Content-Type: application/json" \
  -d '{"material_name":"NaCl"}'
```

Windows (PowerShell):

```powershell
curl.exe -N -X POST "http://localhost:8000/api/analyze" `
  -H "Content-Type: application/json" `
  -d "{\"material_name\":\"NaCl\"}"
```

Notes:
- `-N` keeps the connection open for streaming.
- In PowerShell, use `curl.exe` (PowerShell aliases `curl` to `Invoke-WebRequest` by default).

#### Analyze Debug (full state dump)

macOS/Linux:

```bash
curl -N -X POST "http://localhost:8000/api/analyze-debug" \
  -H "Content-Type: application/json" \
  -d '{"material_name":"NaCl"}'
```

Windows (PowerShell):

```powershell
curl.exe -N -X POST "http://localhost:8000/api/analyze-debug" `
  -H "Content-Type: application/json" `
  -d "{\"material_name\":\"NaCl\"}"
```

#### Debug Graph Structure (prints to server console)

```bash
curl "http://localhost:8000/debug/graph-structure"
```

#### Endpoint Summary

The backend also exposes a lightweight JSON endpoint list at `http://localhost:8000/docs`.

> Note: FastAPI’s default Swagger UI is normally at `/docs`, but this repo currently overrides `/docs` with a custom endpoint summary.

### CLI (status)

- **`chat.py` exists but is currently not aligned with the LangGraph pipeline** (it imports a legacy `run_pipeline` function that is no longer present in `src/orchestrator/main.py`). Use the UI or the API calls above for now.

### Tests

The LangGraph pipeline has a test suite in `src/orchestrator/tests/test_pipeline.py`.

```bash
pytest -q
```

> Some tests and runtime paths require `MP_API_KEY` to be set because `lookup_node` calls Materials Project. You may also need `pip install pytest` if it is not already installed.

---

## 🏗️ Architecture

MatAgent-Forge follows a **client-server architecture** with a Next.js frontend and FastAPI backend:

```text
┌─────────────────┐
│  Next.js UI     │  React/TypeScript, Tailwind CSS
└────────┬────────┘
         │ HTTP (streaming text)
         ▼
┌─────────────────┐
│  FastAPI Server │  Async endpoints + CORS
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│     LangGraph Orchestrator          │
│  lookup → validate → analyze →      │
│  hypothesize → format → (error)     │
└─────────────────────────────────────┘
```

### Project Structure (current)

```text
MatAgent-Forge/
├── app/                          # Next.js app router
├── components/                   # UI components
│   ├── chat-interface.tsx
│   ├── DataPanel.tsx
│   ├── error-boundary.tsx
│   ├── gemini-adapter.tsx
│   ├── LoadingIndicator.tsx
│   └── MarkdownRenderer.tsx
├── rules/                        # Rule database (JSON)
│   ├── extracted_rules.json
│   ├── rule_index.json
│   ├── rule_metadata.json
│   └── rule_validation.json
├── src/
│   ├── agents/
│   │   ├── data_agent.py
│   │   ├── analysis_agent.py
│   │   ├── hypothesis_agent.py
│   │   └── simulation_agent.py
│   ├── data_sources/
│   │   ├── main_orchestrator.py
│   │   ├── paper_scraper.py
│   │   ├── rule_extractor.py
│   │   ├── rule_loader.py
│   │   ├── rule_scoring.py
│   │   └── rule_storage.py
│   └── orchestrator/
│       ├── main.py               # FastAPI app (LangGraph-backed)
│       ├── pipeline_state.py     # PipelineState TypedDict
│       ├── pipeline_graph.py     # StateGraph definition + compile helpers
│       ├── graph_nodes.py        # Node implementations
│       ├── graph_edges.py        # Conditional routing functions
│       ├── guardrails.py         # Chemistry/stability guardrails
│       ├── formatter.py          # Markdown report assembly
│       ├── materials_api.py      # Materials Project wrapper (mp-api)
│       └── tests/
│           └── test_pipeline.py
├── chat.py                       # Legacy CLI (not currently wired)
├── requirements.txt
├── package.json
└── README.md
```

---

## 🚀 Features (backed by current code)

### Core Capabilities
- **📊 Materials Project lookup**: fetch key properties via `mp-api` (`src/orchestrator/materials_api.py`)
- **🧪 Chemistry guardrails**: basic schema/structure presence checks (`src/orchestrator/guardrails.py`)
- **🧩 Property analysis**: deterministic analysis with optional rule-backed insights (`src/agents/analysis_agent.py`)
- **💡 Hypothesis generation**: deterministic hypotheses from properties (`src/agents/hypothesis_agent.py`)
- **📝 Markdown report output**: tables + analysis + hypotheses (`src/orchestrator/formatter.py`)
- **⚡ Streaming API response**: `StreamingResponse` from FastAPI (`src/orchestrator/main.py`)

### Rule Engine
- **📚 Paper scraping**: arXiv + PMC (`src/data_sources/paper_scraper.py`)
- **🧠 Quantitative rule extraction**: LLM-driven extraction via Groq with standardized schema (`src/data_sources/rule_extractor.py`)
- **📦 Rule storage/indexing**: JSON persistence + multi-dimensional indexing + validation (`src/data_sources/rule_storage.py`)
- **🔎 Rule matching**: retrieve relevant rules by property/keywords/domain (`src/data_sources/rule_loader.py`)
- **✅ Schema validation**: Comprehensive validation with array field handling and backward compatibility

### Simulation Agent (experimental)
- **🔬 M3GNet-based feasibility module** exists (`src/agents/simulation_agent.py`) and can attach literature rules, but it is **not currently routed by the LangGraph pipeline**.

---

## 📚 Paper Scraper & Rule Engine (Phase 1a)

MatAgent-Forge includes an automated paper scraper that extracts **quantitative, domain-aware rules** from research paper abstracts and stores them in `rules/`.

### Using the Paper Scraper

Run the full pipeline (scrape → extract → store):

```bash
python -m src.data_sources.main_orchestrator --limit 10 --source arxiv --samples 5
```

Arguments:
- **`--limit N`**: max papers per source (default: 10)
- **`--source`**: `arxiv`, `pmc`, or `both` (default: `arxiv`)
- **`--keywords`**: optional custom keywords (space-separated list)
- **`--samples N`**: number of sample rules to print (default: 5)

Outputs:
- `rules/extracted_rules.json`: extracted rules (with quantitative metadata)
- `rules/rule_metadata.json`: source paper metadata + extraction metadata
- `rules/rule_index.json`: searchable index
- `rules/rule_validation.json`: cross-paper validation bookkeeping

### Rule Categories Extracted
- **Material-property relationships** (quantitative thresholds)
- **Stability indicators** (formation energy / energy above hull bounds)
- **Synthesis feasibility** (temperature/pressure/processing thresholds when present)
- **Application predictions** (e.g., band gap → optoelectronics)

### Standardized Rule Structure (Latest Update)

The rule extraction pipeline now outputs rules in a **standardized, comprehensive schema** that includes all quantitative and metadata fields:

#### Complete Rule Schema

```json
{
  "rule_text": "Human-readable rule statement",
  "rule_type": "chemical_constraint|stability|band_gap|mechanical|synthesis|phase_stability",
  "property": "specific_property_name (e.g., charge_neutrality, energy_above_hull, band_gap)",
  "threshold_value": numeric_value_or_null,
  "threshold_unit": "unit (e.g., eV/atom, GPa, °C, dimensionless)",
  "operator": "=|>|<|>=|<=|range",
  "range_start": numeric_or_null,
  "range_end": numeric_or_null,
  "application": "Specific use case or implication",
  "domain": ["list", "of", "applicable", "domains"],
  "category": "stability|material_property|property_application|synthesis",
  "evidence_strength": "strong|medium|weak",
  "statistical_confidence": 0.0-1.0,
  "confidence": 0.0-1.0,
  "uncertainty": 0.0-1.0,
  "source_paper_id": "arxiv_url",
  "source_section": "abstract|introduction|results|discussion",
  "publication_year": YYYY,
  "validation_status": "physics_based|validated|extracted",
  "rule_id": "rule_XXXXXX",
  "edge_cases": ["list", "of", "exceptions"],
  "fails_for": ["list", "of", "failure", "cases"],
  "evidence_count": optional_integer,
  "validated_materials": ["optional", "list"]
}
```

#### Key Features

1. **Quantitative Thresholds**: All rules include numeric thresholds with units and operators (`=`, `>`, `<`, `>=`, `<=`, `range`)
2. **Domain Arrays**: Domain is always an array (e.g., `["photovoltaics", "optoelectronics"]`) for multi-domain rules
3. **Uncertainty Calculation**: Automatically calculated as `(1 - confidence)` to ensure consistency
4. **Validation Status**: Automatically determined:
   - `"physics_based"` for fundamental laws (charge neutrality, Pauling rules)
   - `"validated"` if evidence_count > 1000
   - `"extracted"` otherwise
5. **Edge Cases & Failure Modes**: Extracted from paper abstracts to document exceptions
6. **Rule ID Format**: Zero-padded 6-digit format (`rule_000001`, `rule_000002`, etc.)

#### Extraction Enhancements

- **LLM-Powered Parsing**: Uses Groq (Llama-3.1-8b-instant) to extract quantitative thresholds, operators, domains, and edge cases from paper abstracts
- **Schema Validation**: Comprehensive validation ensures all required fields are present and correctly formatted
- **Array Handling**: Proper handling of array fields (domain, edge_cases, fails_for) throughout the storage and indexing system
  - Domain arrays are correctly indexed (each domain item indexed separately)
  - Domain filtering works with array-based domains (checks if domain string is in array)
  - Statistics correctly count each domain item from multi-domain rules
- **Backward Compatibility**: Handles legacy string-based domain fields and converts them to arrays automatically

#### Testing

Test the updated extraction pipeline:

```bash
python test_rule_extraction.py
```

Or run unit tests for domain array handling:

```bash
python test_domain_fix.py
```

---

## 🧬 Rule Integration into the Analysis Pipeline (Phase 1.5)

Rules are loaded at runtime and used to enhance analysis output (when applicable).

### How It Works (current behavior)

#### For Materials Project hits
1. Material properties are retrieved
2. Relevant rules are matched to those properties
3. Analysis includes a **Rule-Based Insights** section (when matches exist)

#### For novel materials
- A Simulation Agent module exists, but the current LangGraph pipeline does not yet branch to it on database misses.

### Example Output (illustrative)

Known material (e.g., NaCl):
- **Electronic Behavior**: Semiconductor with band gap 4.38 eV  
  - Rule: Band gap > 3.0 eV → Optoelectronics
- **Rule-Based Insights**: includes top matching rules with confidence

Novel material (simulation route example, when wired):
- **Verdict**: Not feasible
- **Stoichiometry veto**: Violates charge neutrality heuristic
- **Supporting rules**: shows top rules with confidence

---

## 📊 Technology Stack

### Backend
- **FastAPI** (API + streaming)
- **LangGraph** (state machine orchestration)
- **LangChain + Groq** (LLM access; currently used heavily in rule extraction)
- **mp-api** (Materials Project client)
- **pymatgen** (composition/structure utilities; also used by Simulation Agent)
- **numpy / pandas / scikit-learn** (data handling and scoring utilities)

### Frontend
- **Next.js 14**, **React 18**, **TypeScript**
- **Tailwind CSS**, `@tailwindcss/typography`
- **react-markdown** + **remark-gfm**
- **framer-motion**, **lucide-react**

---

## 🚢 Deployment

### Local Development

Backend:

```bash
uvicorn src.orchestrator.main:app --reload --port 8000
```

Frontend:

```bash
npm run dev
```

### Production Deployment

1. **Backend**: deploy FastAPI app to a Python hosting platform (Railway/Heroku/AWS/etc.)
   - Build: `pip install -r requirements.txt` (plus the additional runtime packages listed in Setup)
   - Start: `uvicorn src.orchestrator.main:app --host 0.0.0.0 --port $PORT`

2. **Frontend**:

```bash
npm run build
npm start
```

3. Update the backend URL in `components/gemini-adapter.tsx` to your production endpoint.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m "Add amazing feature"`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines
- Follow PEP 8 for Python
- Use TypeScript strict mode
- Keep docstrings current
- Add or update tests
- Keep README accurate as architecture evolves

---

## 📝 Known Issues & Limitations (needs review)

- **`chat.py` is currently broken against the new LangGraph backend** (imports a legacy `run_pipeline` symbol).
- **FastAPI Swagger UI is overridden** because `src/orchestrator/main.py` defines a `GET /docs` route (so `/docs` is not the usual Swagger UI).
- **Simulation Agent placeholders**:
  - `SubstitutionProbabilityModel` is referenced but not implemented.
  - Competing phase energies include placeholders.
  - `M3GNet.load()` occurs at import time (heavy; can slow startup).
- **Dependency drift**: `requirements.txt` currently omits some runtime imports (FastAPI, uvicorn, langgraph, typing_extensions, and optional m3gnet).

---

## 🔗 Resources & Acknowledgments

- [Materials Project](https://materialsproject.org/) - materials database
- [Materials Project API](https://next-gen.materialsproject.org/api) - API docs
- [Groq](https://groq.com/) - LLM inference
- [LangChain](https://www.langchain.com/) - LLM app framework
- [pymatgen](https://pymatgen.org/) - materials analysis library
- [M3GNet](https://github.com/materialsvirtuallab/m3gnet) - materials property prediction

---

## 🙏 Support

For questions, issues, or contributions:
- Open an issue on GitHub
- Use GitHub Discussions (if enabled)

---

**⭐ Star this repository if you find it useful!**
