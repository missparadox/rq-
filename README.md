# Requirements Evaluator

## Overview

Requirements Evaluator is a hybrid project with two closely related modes:

- service mode:
  a frontend-backend application for uploading requirement files, creating evaluation jobs, and reading generated reports
- standalone skill mode:
  a model-driven workflow that reads requirement packets, applies the rubric in `.agents/skills/requirements-evaluator`, and produces a Chinese Markdown evaluation report

The repository keeps the scoring rubric in the skill, uses the existing packet builder script to normalize evidence, and stores phase 1 service artifacts on the local filesystem.

## Service Mode

Service mode is split into:

- `backend/`
  FastAPI service, local artifact storage, packet generation, model client integration, and job lifecycle
- `frontend/`
  React + TypeScript + Vite application for the upload flow and evaluation detail flow

Current phase 1 status:

- backend scaffold is in place
- create-or-reuse evaluation flow is implemented
- background runner flow is implemented
- evaluation API endpoints are implemented
- frontend upload experience matches the approved premium landing design
- frontend detail page now renders live pending, running, failed, and succeeded states from the backend
- frontend detail view includes polling, task metadata, report download, and structured result sections

## Frontend Setup

Requirements:

- Node.js 22 or newer
- `corepack` available so `pnpm` can be used without a global install

Install dependencies:

```bash
cd frontend
corepack pnpm install
```

Run the frontend tests:

```bash
cd frontend
corepack pnpm exec vitest run
```

Start the frontend dev server:

```bash
cd frontend
corepack pnpm dev
```

## Backend Setup

Requirements:

- Python 3.11+
- a virtual environment

Install backend dependencies into the worktree-local environment:

```bash
cd backend
../.venv/bin/pip install -e .
```

Run backend tests:

```bash
cd backend
../.venv/bin/python -m pytest -q
```

Start the backend dev server:

```bash
cd backend
../.venv/bin/python -m uvicorn app.main:app --reload
```

## Environment Configuration

Backend configuration currently uses these environment variables:

- `REQUIREMENTS_EVALUATOR_DATA_DIR`
  local directory for runtime artifacts; defaults to `<repo>/data`
- `OPENAI_API_KEY`
  when present, the backend builds the OpenAI-backed model client and calls the OpenAI Responses API
- `OPENAI_MODEL`
  OpenAI model name; defaults to `gpt-5.4`
- `OPENAI_BASE_URL`
  OpenAI API base URL; defaults to `https://api.openai.com/v1`
- `ZHIPU_API_KEY`
  when present and OpenAI is unavailable, the backend builds the Zhipu-backed model client
- `ZHIPU_MODEL`
  Zhipu model name; defaults to `glm-5`
- `ZHIPU_BASE_URL`
  Zhipu API base URL; defaults to `https://open.bigmodel.cn/api/paas/v4`
- `CODEX_MODEL`
  Codex CLI model name; defaults to `gpt-5.4`
- `REQUIREMENTS_EVALUATOR_DEBUG_FALLBACK`
  set to `1` to enable the local debug fallback mode

Current backend behavior:

- runtime priority is `OPENAI_API_KEY` first, then `ZHIPU_API_KEY`, then local `codex` on `PATH`, then `REQUIREMENTS_EVALUATOR_DEBUG_FALLBACK=1`
- if none of those modes is available, backend startup fails fast instead of silently falling back to a placeholder runtime
- OpenAI uses `OPENAI_MODEL` and `OPENAI_BASE_URL`, which default to `gpt-5.4` and `https://api.openai.com/v1`
- Zhipu uses `ZHIPU_MODEL` and `ZHIPU_BASE_URL`, which default to `glm-5` and `https://open.bigmodel.cn/api/paas/v4`
- Codex CLI uses `CODEX_MODEL`, which defaults to `gpt-5.4`, and the exec call has timeout protection
- the debug fallback is only enabled when `REQUIREMENTS_EVALUATOR_DEBUG_FALLBACK=1`

Example backend environment setup for real OpenAI-backed evaluations:

```bash
export OPENAI_API_KEY=your-api-key
export OPENAI_MODEL=gpt-5.4
export OPENAI_BASE_URL=https://api.openai.com/v1
```

## Running the Service

Start the backend in one terminal:

```bash
export OPENAI_API_KEY=your-api-key
export OPENAI_MODEL=gpt-5.4
export OPENAI_BASE_URL=https://api.openai.com/v1
cd backend
../.venv/bin/python -m uvicorn app.main:app --reload
```

Start the frontend in another terminal:

```bash
cd frontend
corepack pnpm dev
```

Current HTTP endpoints:

- `POST /api/evaluations`
- `GET /api/evaluations/{evaluation_id}`
- `POST /api/evaluations/{evaluation_id}/retry`

## Local Artifact Storage Behavior

Phase 1 stores artifacts on disk under the configured data directory.

Each evaluation directory contains:

- the original uploaded file
- `metadata.json`
- a generated review packet after runner execution
- a generated Markdown report after successful execution

Dedupe behavior is based on:

- uploaded file content fingerprint
- skill version
- report template version
- model name
- model provider (`openai`, `zhipu`, `codex`, or `debug`)
- app version

Matching `pending`, `running`, and `succeeded` tasks are reusable. Matching `failed` tasks are not reused.

## Standalone Skill Mode

You can use the repository without the service by invoking the requirement evaluator skill directly.

### One-Command End-to-End Evaluation

Use the application-level external runtime runner when you want one command to both invoke the model and produce the final report.

Full-packet prompt flow:

```bash
PYTHONPATH=backend python3 -m app.runners.external_requirements_runner \
  --input requirements.xlsm \
  --review-mode full
```

Split-per-OR prompt flow:

```bash
PYTHONPATH=backend python3 -m app.runners.external_requirements_runner \
  --input requirements.xlsm \
  --review-mode split
```

Both modes write artifacts to the same fixed directory:

- `reports/<input-file-stem>/full-packet.md`
- `reports/<input-file-stem>/packets/`
- `reports/<input-file-stem>/results/`
- `reports/<input-file-stem>/report-full.md` or `report-split.md`
- `reports/<input-file-stem>/report.md` as the latest synced final report

Flow differences:

- `full`: build one full packet -> load the consolidated evaluation standard and report template -> one model call -> one final report
- `split`: one whole input -> split one packet per OR -> one model call per OR -> local aggregation -> one final report

The packet builder script is:

```bash
python3 .agents/skills/requirements-evaluator/scripts/evaluate_requirements.py \
  --input /path/to/input-file.xlsx \
  --packet-scope all-or
```

This keeps the input as one whole file, but the script splits it into one packet per OR. The output directory contains:

- `index.md` or `index.json`
- one `or-*.md` or `or-*.json` file per OR

By default, artifacts are written under a fixed per-input directory in the project:

- `reports/<input-file-stem>/packets/`
- `reports/<input-file-stem>/results/`
- `reports/<input-file-stem>/report.md`

Example:

- `requirements.xlsm` -> `reports/requirements/packets/`

Only OR rows whose `需求分类` is `功能` are included in scoring packets. Other categories are kept only for category statistics and are excluded from scoring.

Each single-OR packet includes:

- that OR and its linked DRs only
- the rubric-derived score skeleton
- compact dimension anchors and red-line rules extracted for split review
- a compact tagged-text result contract: dimension scores use short evidence phrases; totals and grades are calculated locally

The model should then read for each OR packet:

- the generated single-OR packet

For full-packet review over all OR units, the model should still read:

- `.agents/skills/requirements-evaluator/references/default-rubric.md`
- `.agents/skills/requirements-evaluator/references/report-template.md`
- the generated full packet

Normal full-context review does not require reading script source, tests,
`backend/`, `frontend/`, or the skill body again after the workflow has been
loaded. Read implementation source only to diagnose an execution failure that
cannot be resolved from its error message.

Expected output:

- one structured per-OR result, then a locally merged Chinese Markdown evaluation report

After the per-OR model outputs are ready, merge them locally:

```bash
python3 .agents/skills/requirements-evaluator/scripts/aggregate_or_results.py \
  --input /path/to/input-file.xlsx \
  --results-dir /path/to/model-results
```

If `--results-dir` and `--output` are omitted, the aggregator defaults to:

- `reports/<input-file-stem>/results/`
- `reports/<input-file-stem>/report.md`

The aggregator:

- rebuilds OR/DR grouping from the original whole-file input
- parses either strict JSON or the tagged-text fallback result format
- validates OR coverage
- computes overall statistics locally
- renders the final Chinese Markdown report without sending the full source back into the model

If you still want manual control, you can keep using `evaluate_requirements.py` + `aggregate_or_results.py` directly. The application-level external runtime runner just orchestrates those steps automatically.

## Integrating the Skill

The repository keeps the evaluator rubric and template in the skill directory so coding agents can invoke the same review standard both inside and outside service mode.

### OpenCode

For split per-OR review, point the model only at:

- a generated `or-*.md` packet file

For full review over all OR units, additionally provide:

- `.agents/skills/requirements-evaluator/references/default-rubric.md`
- `.agents/skills/requirements-evaluator/references/report-template.md`
- the generated full packet file

### Codex

Use the same skill assets from the repo workspace. The recommended pattern is:

- build split per-OR packets with the script from the whole input file
- review each self-contained `or-*.md` packet without loading references
- instruct Codex to return structured per-OR results first
- merge those per-OR results locally into the final report

For explicit full-context review, load the consolidated evaluation standard,
report template, and full packet together.

### Claude Code

Invoke the repository skill and use its split workflow by default: read one
self-contained `or-*.md` packet at a time and aggregate the saved OR results
locally. For explicit full-context review, read only
`references/default-rubric.md`, `references/report-template.md`, and the
generated full packet before producing the final Chinese Markdown report.
