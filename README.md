# MatAgent-Forge: AI-Powered Materials Science Discovery Platform

MatAgent-Forge is a modern, physics-aware multi-agent system designed to accelerate materials science discovery through intelligent material property analysis, hypothesis generation, and feasibility assessment. The platform combines Large Language Models (LLMs) with computational materials science tools to provide real-time insights into material properties and potential applications.

## 🏗️ Architecture

MatAgent-Forge follows a **client-server architecture** with a Next.js frontend and FastAPI backend, orchestrated by a multi-agent system:

```
┌─────────────────┐  
│  Next.js UI     │  ← React/TypeScript, Tailwind CSS, Real-time Streaming
└────────┬────────┘
         │ HTTP/REST
         ▼
┌─────────────────┐
│  FastAPI Server │  ← Python, Async Streaming, CORS-enabled
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│      Orchestrator Pipeline          │
│  ┌───────────────────────────────┐  │
│  │  Data Agent                   │  │  ← Materials Project API queries
│  │  ↓                            │  │
│  │  Analysis Agent               │  │  ← Property analysis (electronic, mechanical, thermal)
│  │  ↓                            │  │
│  │  Hypothesis Agent             │  │  ← Application hypothesis generation
│  │  ↓                            │  │
│  │  Formatter                    │  │  ← Markdown report assembly
│  └───────────────────────────────┘  │
│            OR                        │
│  ┌───────────────────────────────┐  │
│  │  Simulation Agent             │  │  ← M3GNet-based feasibility (database misses)
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

## 🚀 Features

### Core Capabilities

- **📊 Material Property Lookup**: Query Materials Project database for comprehensive material data including crystal structure, band gaps, formation energies, and mechanical properties
- **🧩 Intelligent Analysis**: Multi-dimensional property analysis covering:
  - **Electronic Behavior**: Band gap analysis, semiconductor/metallic classification
  - **Mechanical Behavior**: Bulk modulus, shear modulus assessment
  - **Thermal Behavior**: Thermal property evaluation (when available)
  - **Stability Assessment**: Energy above hull analysis for phase stability
- **🔭 Hypothesis Generation**: AI-driven hypothesis generation suggesting potential applications based on material properties:
  - Optoelectronics (UV/IR sensors, LEDs)
  - Thermoelectric devices
  - Structural materials (aerospace, lightweight applications)
  - Conductive layers and contacts
- **🔬 Simulation-Based Feasibility**: For materials not in databases, uses M3GNet (Materials 3D Graph Network) for:
  - Structure prototype generation (Rock-salt, Perovskite, Spinel)
  - Formation energy prediction
  - Convex hull stability analysis
  - Chemical feasibility checks (electronegativity, stoichiometry, crystal chemistry)

### User Interface

- **💬 Real-time Chat Interface**: Modern, responsive chat UI with streaming responses
- **📝 Markdown Rendering**: Beautifully formatted reports with tables, code blocks, and scientific notation
- **⚡ Streaming Responses**: Live updates as analysis progresses through pipeline steps
- **🎨 Modern Design**: Dark theme optimized for scientific content visualization

### Developer Experience

- **🔌 RESTful API**: Well-documented FastAPI endpoints for integration
- **🖥️ CLI Interface**: Command-line tool (`chat.py`) for direct pipeline execution
- **📦 Modular Architecture**: Clean separation of concerns with specialized agents

## 📁 Project Structure

```
MatAgent-Forge/
│
├── app/                          # Next.js application
│   ├── page.tsx                  # Main application page
│   ├── layout.tsx                # Root layout with metadata
│   ├── globals.css               # Global styles
│   └── demo/                     # Demo pages (optional)
│
├── components/                   # React components
│   ├── chat-interface.tsx        # Main chat UI component
│   ├── gemini-adapter.tsx        # Backend API adapter
│   ├── error-boundary.tsx        # Error handling component
│   ├── LoadingIndicator.tsx      # Loading state component
│   └── MarkdownRenderer.tsx      # Markdown display utilities
│
├── src/                          # Python backend
│   ├── agents/                   # Multi-agent system
│   │   ├── data_agent.py         # Materials Project API integration
│   │   ├── analysis_agent.py     # Property analysis (LLM: Llama-3.3-70b)
│   │   ├── hypothesis_agent.py   # Hypothesis generation
│   │   └── simulation_agent.py   # M3GNet-based feasibility assessment
│   │
│   └── orchestrator/             # Pipeline orchestration
│       ├── main.py               # FastAPI app & pipeline coordinator
│       ├── formatter.py          # Markdown report generation
│       └── materials_api.py      # Materials Project API wrapper
│
├── chat.py                       # CLI interface for pipeline
│
├── requirements.txt              # Python dependencies
├── package.json                  # Node.js dependencies
├── tsconfig.json                 # TypeScript configuration
├── tailwind.config.js            # Tailwind CSS configuration
│
└── README.md                     # This file
```

## 🔧 Installation

### Prerequisites

- **Python 3.10+** (Python 3.11+ recommended for optimal compatibility)
- **Node.js 18+** and npm
- **Materials Project API Key** ([Get one here](https://next-gen.materialsproject.org/api))
- **Groq API Key** ([Get one here](https://console.groq.com/))

### Backend Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/A5hwIN101/MatAgent-Forge
   cd MatAgent-Forge
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   
   **Note**: The codebase also uses the following packages which should be installed:
   ```bash
   pip install fastapi uvicorn m3gnet
   ```

4. **Configure environment variables**
   
   Create a `.env` file in the root directory:
   ```env
   MP_API_KEY=your_materials_project_api_key
   GROQ_API_KEY=your_groq_api_key
   ```

### Frontend Setup

1. **Install Node.js dependencies**
   ```bash
   npm install
   ```

2. **Configure backend URL** (if deploying frontend separately)
   
   Edit `components/gemini-adapter.tsx` and update:
   ```typescript
   const BACKEND_URL = "http://localhost:8000";  // Default for local development
   ```

## 🛠️ Usage

### Running the Full Stack Application

1. **Start the FastAPI backend**
   ```bash
   # From the root directory
   uvicorn src.orchestrator.main:app --reload --port 8000
   ```
   
   Or navigate to the orchestrator directory:
   ```bash
   cd src/orchestrator
   uvicorn main:app --reload --port 8000
   ```

2. **Start the Next.js frontend** (in a separate terminal)
   ```bash
   npm run dev
   ```

3. **Access the application**
   - Frontend: http://localhost:3000
   - API Docs: http://localhost:8000/docs (FastAPI automatic documentation)

### Command-Line Interface

For direct pipeline execution without the web interface:

```bash
python chat.py
```

Then enter material formulas when prompted (e.g., `NaCl`, `Fe2O3`, `MgO`). Type `exit` to quit.

### API Usage

#### Analyze Material Endpoint

```bash
curl -X POST "http://localhost:8000/api/analyze" \
  -H "Content-Type: application/json" \
  -d '{"material_name": "NaCl"}'
```

The endpoint returns a streaming response with markdown-formatted analysis.

## 🔍 How It Works

### Pipeline Flow

1. **User Input**: Material formula entered (e.g., "NaCl", "Fe2O3")
2. **Data Agent**: Queries Materials Project API for material properties
3. **Decision Point**: 
   - **If found in database** → Analysis Agent → Hypothesis Agent → Formatted Report
   - **If not found** → Simulation Agent → Feasibility Assessment → Simulation Report
4. **Response**: Streamed markdown report with:
   - Material summary (formula, structure, space group)
   - Computed properties table
   - Multi-dimensional analysis
   - Generated hypotheses and applications

### Agent Details

#### Data Agent (`data_agent.py`)
- **Purpose**: Interface with Materials Project API
- **LLM**: Llama-3.1-8b-instant (lightweight, fast)
- **Output**: Dictionary of material properties

#### Analysis Agent (`analysis_agent.py`)
- **Purpose**: Deep property analysis
- **LLM**: Llama-3.3-70b-versatile (heavy model for reasoning)
- **Analysis Dimensions**:
  - Electronic behavior (band gap → semiconductor/metallic)
  - Mechanical behavior (bulk modulus, shear modulus)
  - Thermal behavior (when available)
  - Stability (energy above hull)

#### Hypothesis Agent (`hypothesis_agent.py`)
- **Purpose**: Generate application-oriented hypotheses
- **Logic**: Rule-based system analyzing:
  - Band gap → optoelectronics applications
  - Stability → synthesis feasibility
  - Density → structural applications
  - Crystal system → anisotropic properties

#### Simulation Agent (`simulation_agent.py`)
- **Purpose**: Feasibility assessment for unknown materials
- **Tools**: 
  - M3GNet (graph neural network for formation energy)
  - pymatgen (crystal structure, phase diagrams)
  - Chemical feasibility filters (electronegativity, stoichiometry, ionic radii)
- **Workflow**:
  1. Stoichiometry validation
  2. Chemical feasibility checks
  3. Structure prototype generation
  4. M3GNet energy prediction
  5. Convex hull stability (if competing phases available)
  6. Verdict: Feasible / Metastable / Not Feasible

---

## 📚 Paper Scraper & Rule Engine (Phase 1a)

MatAgent-Forge now includes an automated paper scraper that extracts domain knowledge from research papers to power its rule engine.

### Features
- **Paper Scraping**: Query arXiv and PubMed Central (PMC) for materials science research
- **Rule Extraction**: Use LLM to extract actionable rules from paper abstracts
- **Rule Storage**: Persistent JSON-based rule database with indexing and search
- **Rule Loading**: Cache rules in-memory for fast access during analysis

### Rule Categories Extracted
- **Material-Property Relationships**: e.g., "High band gap → optoelectronics"
- **Stability Indicators**: e.g., "Materials with negative formation energy are stable"
- **Synthesis Feasibility**: e.g., "Perovskites require specific stoichiometric ratios"
- **Application Predictions**: e.g., "Semiconductors with Eg 3-5eV for UV detectors"

### Using the Paper Scraper

**Run the full pipeline** (scrape → extract → store):
```bash
conda activate matagent310
python -m src.data_sources.main_orchestrator --limit 10 --source arxiv
```

**Arguments:**
- `--limit N`: Maximum number of papers to scrape (default: 10)
- `--source [arxiv|pmc|both]`: Which source to scrape (default: arxiv)
- `--keywords`: Custom keywords (default: materials science related)
- `--samples`: Show sample rules after extraction (default: True)

**Output:**
- `rules/extracted_rules.json` - All extracted rules with metadata
- `rules/rule_metadata.json` - Paper sources and extraction metadata
- `rules/rule_index.json` - Searchable index by category and keyword

### Integration with Analysis Agent

Rules are automatically loaded at startup and used to improve hypothesis generation:
```python
from src.data_sources.rule_loader import RuleLoader

loader = RuleLoader()
relevant_rules = loader.get_rules_for_analysis(material_properties)
# Use relevant_rules to enhance analysis
```

### Project Structure
src/data_sources/
├── paper_scraper.py      # arXiv & PMC API wrapper
├── rule_extractor.py     # LLM-based rule extraction
├── rule_storage.py       # JSON rule persistence & indexing
├── rule_loader.py        # Rule loading & caching
└── main_orchestrator.py  # CLI pipeline coordinator  
rules/
├── extracted_rules.json  # All extracted rules
├── rule_metadata.json    # Paper metadata
└── rule_index.json       # Searchable index

---

## 🧬 Rule Integration into Analysis Pipeline (Phase 1.5)

MatAgent-Forge now integrates extracted rules into the Analysis and Simulation Agents for evidence-backed material analysis.

### Features
- **Rule-Enhanced Analysis**: Analysis Agent references extracted rules for known materials
- **Rule-Based Simulation**: Simulation Agent uses rules     feasibility assessment of novel materials
- **Rule-Backed Verdicts**: Simulation verdicts reference supporting literature rules
- **Confidence Scoring**: Each rule shows confidence level (0.0 - 1.0)

### How It Works

#### For Known Materials (Materials Project Database)
1. Material properties are analyzed
2. Relevant rules are matched to those properties
3. Analysis includes "Rule-Based Insights" section
4. Hypotheses reference rules for evidence

#### For Novel Materials (Simulation)
1. Feasibility is assessed using rules
2. Violations reference specific rules
3. Verdicts show supporting rules with confidence
4. Better decision-making with literature backing

### Example Output

**Known Material (NaCl):**
Electronic Behavior: Semiconductor with band gap 4.38 eV
Rule: Band gap > 3.0 eV → Optoelectronics
Rule-Based Insights:
• Band gap > 3.0 eV → Optoelectronics (confidence: 100%)
• Energy above hull < 0.05 eV/atom → Stable phase (confidence: 100%)

**Novel Material (Cu2N5):**
Verdict: Not feasible
Stoichiometry Veto: Violates charge neutrality rule
Supporting Rules:
• Charge and electronegativity neutrality are chemical guidelines (confidence: 100%)

### Technical Implementation

Rules are loaded at application startup and cached in memory for performance:
- Analysis Agent: Matches rules to material properties during analysis
- Simulation Agent: References rules during feasibility assessment
- Formatter: Displays rules with confidence scores in markdown output

---

## 📊 Technology Stack

### Backend
- **FastAPI**: Modern Python web framework with async support
- **LangChain + Groq**: LLM orchestration (Llama models)
- **pymatgen**: Materials science toolkit
- **mp-api**: Materials Project API client
- **M3GNet**: Graph neural network for materials property prediction
- **numpy, pandas, scikit-learn**: Data processing

### Frontend
- **Next.js 14**: React framework with App Router
- **TypeScript**: Type-safe JavaScript
- **Tailwind CSS**: Utility-first styling
- **React Markdown**: Markdown rendering with GitHub Flavored Markdown
- **Framer Motion**: Smooth animations
- **Lucide React**: Icon library

## 🔐 Environment Variables

Required environment variables (set in `.env` file):

```env
MP_API_KEY=your_materials_project_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

## 🚢 Deployment

### Local Development

For local development, use the commands below:

**Backend:**
```bash
uvicorn src.orchestrator.main:app --reload --port 8000
```

**Frontend:**
```bash
npm run dev
```

### Production Deployment

1. **Backend**: Deploy FastAPI app to any Python hosting platform (Railway, Heroku, AWS, DigitalOcean, etc.)
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn src.orchestrator.main:app --host 0.0.0.0 --port $PORT`

2. **Frontend**: Build and deploy Next.js app:
   ```bash
   npm run build
   npm start
   ```

3. **Update Backend URL**: After deploying the backend, update `BACKEND_URL` in `components/gemini-adapter.tsx` to point to your production API endpoint.

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 for Python code
- Use TypeScript strict mode for frontend code
- Add docstrings to all functions
- Update tests when adding features
- Keep the README updated with new features

## 📝 Known Issues & Limitations

- **SubstitutionProbabilityModel**: Referenced in `simulation_agent.py` but not yet implemented (uses placeholder logic)
- **M3GNet Dependencies**: Requires additional dependencies that may need manual installation
- **Competing Phases Library**: Limited to common binary/ternary systems; extend for broader coverage
- **Error Handling**: Some edge cases in material formula parsing may need refinement

## 🔗 Resources & Acknowledgments

- [Materials Project](https://materialsproject.org/) - Comprehensive materials database
- [Materials Project API](https://next-gen.materialsproject.org/api) - API documentation
- [Groq](https://groq.com/) - Fast LLM inference platform
- [LangChain](https://www.langchain.com/) - LLM application framework
- [pymatgen](https://pymatgen.org/) - Materials analysis library
- [M3GNet](https://github.com/materialsvirtuallab/m3gnet) - Materials property prediction

## 🙏 Support

For questions, issues, or contributions:
- Open an issue on GitHub
- Check existing discussions in GitHub Discussions
- Review the API documentation at `/docs` endpoint when running locally

---

## 📋 Development Progress

### Completed Phases

#### Rule Extraction & Integration (Phase 1a - 1.5b)
- ✅ **Phase 1a**: Paper Scraper - Extract rules from arXiv/PMC papers
- ✅ **Phase 1a+**: Rule Quality Improvement - Quantitative, domain-aware rules with statistical confidence
- ✅ **Phase 1.5**: Rules integrated into Analysis Agent for known materials
- ✅ **Phase 1.5b**: Rules integrated into Simulation Agent for novel materials

#### LangGraph State Machine Architecture (Phase 1.5c) - NEW ✨
- ✅ **Explicit State Management**: PipelineState TypedDict for single source of truth
- ✅ **6-Node StateGraph**: `lookup → validate_chemistry → analyze → hypothesize → format → END`
- ✅ **Conditional Edge Routing**: Intelligent error handling with branch logic
- ✅ **Async Pipeline**: All agents wrapped as async functions for non-blocking execution
- ✅ **Streaming Support**: FastAPI integration with real-time markdown output
- ✅ **Comprehensive Testing**: 12/12 tests passing (state, routing, nodes, full pipeline)

**Key Improvements:**
- 🔍 **Debugging**: Full state visibility at each node (no black-box execution)
- 🛡️ **Error Recovery**: Conditional edges route failures to error handlers gracefully
- 🚀 **Performance**: Async operations enable scaling to 100+ concurrent requests
- 📦 **Modularity**: Nodes are self-contained, making Phase 2/3 additions seamless
- 📊 **Observability**: Detailed logging at each step for production monitoring

**Architecture Highlights:**
```
Input (formula)
↓
[lookup_node] → Query Materials Project API
↓
[validate_chemistry_node] → Check chemistry guardrails
├─ Valid? → [analyze_node] → Analyze properties
│                ↓
│          [hypothesize_node] → Generate hypotheses
│                ↓
│           [format_node] → Create markdown output
│                ↓
└─────────────→ END (success)
│
└─ Invalid? → [error_node] → Handle gracefully
↓
END (error)
```

### Current Status
- ✅ **LangGraph Pipeline**: Production-ready state machine with 6 nodes
- ✅ **Rule Integration**: 24 quantitative rules extracted (87.5% high confidence ≥0.8)
- ✅ **Test Coverage**: 12 unit tests covering state, routing, nodes, and full pipeline
- ✅ **API Streaming**: Real-time markdown responses with 9+ rules displayed
- ✅ **Material Analysis**: Successfully analyzed NaCl with electronic, mechanical, and stability insights

**Domains covered:** Photovoltaics, thermoelectric, battery, structural, optoelectronics, general

### Next Phases
- 🔄 **Phase 2**: OQMD Integration - Add fallback material source, expand rule database
  - New conditional edge: if MP API fails → try OQMD
  - Existing nodes unchanged (demonstrates modularity)
- 🔄 **Phase 3**: ICSD Integration - Experimental crystal structure data
- 🔄 **Phase 4**: Production Hardening - LangSmith tracing, checkpointing, compliance audit

---

**⭐ Star this repository if you find it useful!**
