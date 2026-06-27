# COBOL/Telon to Spring Boot + Next.js Migration Automation

Automated iterative migration pipeline that converts mainframe COBOL/Telon programs to modern Spring Boot (Java) backend and Next.js (TypeScript/React) frontend with **>95% accuracy**.

## How It Works

```
┌─────────────────┐     ┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│  COBOL/Telon    │────▶│  LLM-Based   │────▶│   Accuracy    │────▶│   Output     │
│  Source File    │     │  Conversion  │     │   Analysis    │     │   Files      │
└─────────────────┘     └──────────────┘     └───────────────┘     └──────────────┘
                              ▲                      │
                              │    < 95% accuracy    │
                              └──────────────────────┘
                                (Iterative Refinement)
```

### Pipeline Steps:
1. **Parse** - Extract COBOL structure (paragraphs, fields, screen maps, validations, DB ops)
2. **Convert** - LLM generates Spring Boot + Next.js code from COBOL source
3. **Analyze** - Compare generated code against original (6 accuracy dimensions)
4. **Refine** - If <95%, feed gaps back to LLM for targeted fixes
5. **Repeat** - Loop until target accuracy or max iterations reached

### Accuracy Dimensions:
| Dimension | Weight | What's Checked |
|-----------|--------|---------------|
| Business Logic | 25% | Paragraphs → methods, EVALUATE/IF logic, PERFORM loops |
| Schema Mapping | 20% | COPYBOOK → entities, table names, CRUD operations |
| Error Handling | 15% | Error conditions, exception flows, error recovery |
| Field Validations | 15% | NUMERIC checks, SPACES checks, length/range validations |
| UI Fields | 15% | Screen fields → React components, field types, labels |
| Error Messages | 10% | Message literals preserved exactly in output |

## Setup

```bash
cd cobol-migration-automation
pip install -r requirements.txt
```

### Configure API Access

Copy `.env.example` to `.env` and fill in your API credentials:

```bash
copy .env.example .env
```

Then edit `.env` with your provider details:

```env
# Choose one provider: openai | azure | anthropic
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o
```

## Usage

### Basic Usage
```bash
python run.py input/MY_PROGRAM.cbl
```

### With Options
```bash
# Use Azure OpenAI with custom iterations
python run.py input/MY_PROGRAM.cbl --provider azure --max-iterations 15

# Set lower accuracy target for faster results
python run.py input/MY_PROGRAM.cbl --target-accuracy 90

# Override API key and model
python run.py input/MY_PROGRAM.cbl --api-key sk-... --model gpt-4o

# Custom output directory
python run.py input/MY_PROGRAM.cbl --output ./my_output
```

### Command Line Arguments
| Argument | Default | Description |
|----------|---------|-------------|
| `input_file` | (required) | Path to COBOL/Telon source file |
| `--provider` | from .env | LLM provider: openai, azure, anthropic |
| `--max-iterations` | 10 | Maximum refinement iterations |
| `--target-accuracy` | 95 | Target accuracy percentage |
| `--output` | ./output | Output directory for generated files |
| `--api-key` | from .env | API key override |
| `--model` | from .env | Model name override |
| `--max-tokens` | 4096 | Max tokens per LLM call |

## Run with Docker (Recommended for EC2)

### 1) Build image
```bash
docker build -t cobol-migration-automation:latest .
```

### 2) Run with mounted input/output folders
```bash
docker run --rm \
  --env-file .env \
  -v "$(pwd)/input:/app/input" \
  -v "$(pwd)/output:/app/output" \
  cobol-migration-automation:latest input/YOUR_PROGRAM.txt
```

> Use `.txt`, `.cbl`, or listing files as input. The pipeline auto-detects compiler listing format.

## Run with Docker Compose

### 1) Build
```bash
docker compose build
```

### 2) Execute migration
```bash
docker compose run --rm migrator input/YOUR_PROGRAM.txt
```

### 3) Output
Generated files are written to local `./output` (mounted to `/app/output` in container).

## EC2 Quick Start

1. Launch Ubuntu EC2, install Docker + Docker Compose.
2. Clone this repo on EC2.
3. Create `.env` with your provider/API settings.
4. Copy input files into `input/`.
5. Run:
   ```bash
   docker compose build
   docker compose run --rm migrator input/YOUR_PROGRAM.txt
   ```

## CI/CD (GitHub Actions)

Workflow file: `.github/workflows/ci-cd.yml`

### CI on PR / Push
- Install dependencies
- Compile check (`python -m compileall`)
- CLI smoke test (`python run.py --help`)
- Docker image build test

### CD on push to `main`
- Builds and pushes image to GHCR:
  - `ghcr.io/<org-or-user>/cobol-migration-automation:latest`
  - `ghcr.io/<org-or-user>/cobol-migration-automation:<git-sha>`
- Optional EC2 deploy runs automatically if these GitHub secrets are set:
  - `EC2_HOST`
  - `EC2_USER`
  - `EC2_SSH_KEY`
  - `EC2_APP_PATH` (path on EC2 where `docker-compose.yml` exists)

## Output Structure

```
output/
└── PROGRAM_NAME/
    ├── migration_report.json          # Structured accuracy report
    ├── src/main/java/com/app/
    │   ├── entity/                    # JPA entities from COPYBOOKs
    │   ├── repository/                # Spring Data JPA repositories
    │   ├── service/                   # Business logic (from COBOL paragraphs)
    │   ├── controller/                # REST API controllers
    │   ├── dto/                       # Request/Response DTOs
    │   └── exception/                 # Custom exceptions
    └── src/
        ├── app/                       # Next.js pages
        ├── components/                # React components (from Telon screens)
        └── types/                     # TypeScript interfaces
```

## Architecture

```
cobol-migration-automation/
├── config/
│   ├── settings.py              # Configuration (env vars, weights)
│   └── prompts/                 # LLM prompt templates
│       ├── conversion_prompts.py
│       └── analysis_prompts.py
├── src/
│   ├── orchestrator.py          # Main pipeline controller
│   ├── llm/                     # Pluggable LLM providers
│   │   ├── base.py              # Abstract interface
│   │   ├── openai_provider.py   # OpenAI GPT-4o
│   │   ├── azure_provider.py    # Azure OpenAI
│   │   └── anthropic_provider.py # Anthropic Claude
│   ├── parser/                  # COBOL/Telon structural parser
│   │   └── cobol_parser.py
│   ├── converter/               # LLM-based code generator
│   │   └── code_converter.py
│   ├── analyzer/                # Accuracy measurement
│   │   └── accuracy_analyzer.py
│   └── reporter/                # Report generation
│       └── migration_report.py
├── input/                       # Place COBOL/Telon files here
├── output/                      # Generated code output
├── run.py                       # CLI entry point
└── requirements.txt
```

## Adding a Custom LLM Provider

Implement the `BaseLLMProvider` interface:

```python
from src.llm.base import BaseLLMProvider, LLMResponse

class MyCustomProvider(BaseLLMProvider):
    def generate(self, system_prompt, user_prompt, max_tokens=4096, temperature=0.2):
        # Your API call here
        return LLMResponse(content=..., model=..., input_tokens=..., output_tokens=..., finish_reason=...)
    
    def generate_with_context(self, system_prompt, messages, max_tokens=4096, temperature=0.2):
        # Your API call with history
        ...
    
    def get_model_name(self):
        return "my-model"
    
    def estimate_tokens(self, text):
        return len(text) // 4
```

Then use it directly:
```python
from src.orchestrator import MigrationOrchestrator

provider = MyCustomProvider(api_key="...")
orchestrator = MigrationOrchestrator(llm_provider=provider)
orchestrator.migrate(Path("input/MY_PROGRAM.cbl"))
```

## Tuning Accuracy Weights

Edit `config/settings.py` to adjust how dimensions are weighted:

```python
ACCURACY_WEIGHTS = {
    "business_logic": 0.25,    # Most important
    "error_handling": 0.15,
    "schema_mapping": 0.20,
    "field_validation": 0.15,
    "ui_fields": 0.15,
    "error_messages": 0.10,
}
```

## Sample Output

```
============================================================
  MIGRATION COMPLETE - FINAL REPORT
============================================================
  Program: CUST-MAINT
  Final Accuracy: 96.2%
  Total Iterations: 3
  Total Tokens Used: 45,230
  Elapsed Time: 127.4s
  Files Generated: 12
============================================================

  ACCURACY PROGRESSION:
    Iteration 1: [████████████░░░░░░░░] 62.5%
    Iteration 2: [████████████████░░░░] 84.3%
    Iteration 3: [███████████████████░] 96.2%

  FINAL DIMENSION SCORES:
    ✓ Business Logic            97.0%
    ✓ Error Handling            95.5%
    ✓ Schema & Table Mapping    98.0%
    ✓ Field Validations         95.0%
    ✓ UI Fields                 96.0%
    △ Error Messages            93.0%
============================================================
```
