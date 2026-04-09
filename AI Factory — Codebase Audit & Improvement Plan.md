  ---
  AI Factory — Codebase Audit & Improvement Plan

  PHASE 1: AUDIT

  ---
  ARCHITECTURE

  Strengths
  - Clear pipeline topology: signal mining → idea generation →
  filtering → validation → matching → offers
  - Good module separation: each workspace script has a single job
   with a CLI entry point
  - LLMRouter centralizes all provider logic; consumers only call
  router.complete() / router.acomplete()
  - --dry-run flag is wired all the way through the stack —
  testable without API keys
  - Atomic writes (.tmp → rename) in connector, matcher, and offer
   generator

  Issues
  - _find_connector_json() is duplicated verbatim in
  matcher.py:239 and offer_generator.py:161. Any change must be
  made twice.
  - workspace/ modules are not a Python package. All consumers do
  sys.path.insert(0, ...) at the top of the file — fragile and
  IDE-hostile.
  - Moneymaker/src/signal_miner/jobboards.py tags both HN and
  Reddit signals as SignalSource.JOBBOARDS. The REDDIT enum value
  exists but is never used here.
  - ai-factory-api/ is a thin FastAPI wrapper over the shell
  script. There is no request validation on run_id, enabling path
  traversal (see Security).

  ---
  CODE QUALITY

  Critical
  - Cerebras model mismatch: PROVIDERS["cerebras"].models =
  ["llama3.1-8b", "llama3.1-8b"] (both slots the 8b model) but
  TASKS["generation"].preferred_model = "llama3.3-70b". In
  _pick_model, the target "llama3.3-70b" is not in the models
  list, so it silently falls back to llama3.1-8b. Generation
  always runs on the smaller model, unbeknownst to the caller.
  - asyncio.get_event_loop() at llm_router.py:515 — deprecated in
  Python 3.10+ when called outside a running loop. Should be
  asyncio.get_running_loop().

  Moderate
  - _bootstrap_env() in llm_router.py fires 4–5 print() calls at
  module import time (lines 96–104). Every process that imports
  llm_router (API server, pipeline, tests) will emit this noise to
   stdout.
  - Moneymaker/ test suite is solid (8 test files) but workspace/
  scripts (connector.py, matcher.py, offer_generator.py,
  client_finder.py) have zero tests. These are the integration
  glue; failures here are hard to debug.
  - run_pipeline.sh log message says threshold=0.7 (line 110) but
  connector.py uses SCORE_THRESHOLD = 7.0 (0–10 scale). The
  CLAUDE.md also documents score >= 0.7 in two places — a stale
  0–1 scale reference.

  Minor
  - Moneymaker/test.md is a leftover scratch file in the module
  root.
  - offer_generator.py carries two full flows (primary + legacy
  --from-matches), inflating the file to 584 lines. The legacy
  path is exercised only by a flag, not a test.

  ---
  DOCUMENTATION

  - CLAUDE.md (root) states score >= 0.7 as the connector
  threshold in two places (lines 130, 226). The actual value is
  7.0. This misleads anyone using the spec as ground truth.
  - CLAUDE.md report schema includes ideas_mined and
  ideas_passed_filter fields, but run_pipeline.sh never writes
  them to report.json.
  - Moneymaker/claude.md is lowercase while the rest use CLAUDE.md
   — inconsistent naming.
  - WHITEPAPER.md, ROADMAP.md, PROGRESS.md, AUDIT.md — four
  status/planning docs with potential staleness. No single source
  of truth for current project state.

  ---
  CI/CD & DEVOPS

  - No CI at the repo root. Agent-Guidelines/ and
  ai-knowledge-filler/ both have .github/workflows/ but
  Moneymaker/, workspace/, and ai-factory-api/ have no automated
  testing or linting.
  - requirements.txt (root) lists 13 packages with no pinned
  versions — reproducibility risk.
  - Moneymaker/pyproject.toml contains only
  [tool.pytest.ini_options] — no ruff, mypy, or black config.
  - railway.toml is empty. Procfile starts uvicorn
  ai-factory-api.main:app but there is no requirements.txt or
  pyproject.toml in ai-factory-api/ — deployment to Railway will
  fail without additional config.

  ---
  SECURITY

  1. Moneymaker/.env contains a real CEREBRAS_API_KEY
  (csk-v3rkd5k5...). The file is gitignored and not currently
  tracked, but the key is live and exposed on disk. It should be
  rotated and moved to a secrets manager.
  2. Path traversal in ai-factory-api/main.py: run_id from the URL
   path is used directly in os.path.join(RUNS_DIR, run_id, ...)
  with no sanitization. A caller with a valid API key can request
  run_id = "../../etc" and read arbitrary files accessible by the
  server process.
  3. workspace/runs/ is committed to git (3 run directories
  visible in git ls-files). This persists generated output —
  including connector.json entries with source_url, source_author,
   and source_text scraped from HN/Reddit — in version history.

  ---
  DEPENDENCIES

  - requirements.txt (root) is unpinned — version drift can break
  the pipeline silently.
  - cerebras-cloud-sdk and groq appear in requirements.txt (root)
  but Moneymaker/requirements.txt is separate — two dependency
  files to keep in sync.
  - package-lock.json at root with no package.json — leftover
  artifact.

  ---
  PERFORMANCE & SCALABILITY

  - client_finder.py:196 uses asyncio.gather(*[_fetch_comment(...)
   for k in kid_ids]) where kid_ids = thread.get("kids")[:limit *
  3] — up to 150 concurrent HTTP requests with no semaphore. This
  will hit HN rate limits.
  - The LLMRouter usage tracker is in-process and resets on
  restart. For the FastAPI server running as a long-lived process
  this is fine, but for the shell-invoked pipeline each invocation
   starts fresh with zero usage memory — rate limit tracking is
  ineffective across runs.
  - workspace/offers/ writes are sequential (one LLM call per idea
   per offer_generator.py loop). For large connector.json outputs
  this is slow; no batching or parallelism.

  ---
  PHASE 2: TASKS

  ---
  [P0] Fix path traversal in API run_id parameter

  What: Sanitize run_id in ai-factory-api/main.py before using it
  in filesystem paths.
  Why: An authenticated caller can escape the runs/ directory and
  read arbitrary files.
  How:
  1. Add a validation regex: run_id must match ^run_\d{8}_\d{6}$
  2. After os.path.join, assert the resolved path starts with
  os.path.realpath(RUNS_DIR)
  3. Raise HTTP 400 on mismatch
  Files: ai-factory-api/main.py (lines 37, 101, 112)
  Done when: curl /runs/../../etc returns 400, not 404 or file
  content.
  Effort: XS+

  ---
  [P0] Rotate and remove real Cerebras API key from .env

  What: Remove the live key from Moneymaker/.env and replace with
  a placeholder.
  Why: The live key csk-v3rkd5k5... is in a committed-adjacent
  file on disk.
  How:
  4. Rotate the key at cerebras.ai immediately
  5. Replace the value in Moneymaker/.env with csk-your-key-here
  6. Add a pre-commit hook (or extend the existing gitleaks
  config) to block .env files with real key patterns
  Files: Moneymaker/.env, .gitleaks.toml
  Done when: Moneymaker/.env contains no real credentials; old key
   is revoked.
  Effort: XS+

  ---
  [P0] Add workspace/runs/ and workspace/leads/ to .gitignore

  What: Stop tracking generated pipeline output in git.
  Why: Run outputs (connector.json, ideas.json, logs) containing
  scraped user data are committed to version history and bloat the
   repo.
  How:
  7. Add workspace/runs/, workspace/leads/, workspace/matches/ to
  root .gitignore
  8. Run git rm -r --cached workspace/runs/ workspace/leads/ to
  untrack existing files
  9. Commit the result
  Files: .gitignore
  Done when: git status shows no workspace/runs/ content; git
  ls-files workspace/runs/ returns empty.
  Effort: XS+

  ---
  [P1] Fix Cerebras model mismatch in LLMRouter

  What: The generation task requests llama3.3-70b but the Cerebras
   provider only lists llama3.1-8b.
  Why: _pick_model falls back silently to llama3.1-8b; the
  preferred model for generation is never actually used, degrading
   output quality without any warning.
  How:
  10. Either update PROVIDERS["cerebras"].models to include
  "llama3.3-70b" if it is available, OR update
  TASKS["generation"].preferred_model to "llama3.1-8b" to match
  reality
  11. Add a startup assertion: assert task.preferred_model in
  provider.models or provider is not task.preferred_provider
  Files: workspace/llm_router.py (lines 144, 201)
  Done when: router.status() confirms the generation task runs on
  the intended model.
  Effort: XS+

  ---
  [P1] Fix score threshold documentation and log message

  What: Correct the three places where 0.7 is used instead of 7.0
  as the connector score threshold.
  Why: CLAUDE.md (lines 130, 226) and run_pipeline.sh (line 110)
  reference 0.7 — a stale 0–1 scale value — while connector.py
  correctly uses 7.0 on a 0–10 scale. Misleads anyone reading the
  spec.
  How:
  12. Update CLAUDE.md lines 130 and 226: score >= 0.7 → score >=
  7.0
  13. Update run_pipeline.sh line 110 log: threshold=0.7 →
  threshold=7.0
  Files: CLAUDE.md, run_pipeline.sh
  Done when: All three references say 7.0.
  Effort: XS+

  ---
  [P1] Extract _find_connector_json to a shared workspace utility

  What: Remove the duplicated function present identically in
  matcher.py:239 and offer_generator.py:161.
  Why: Duplication means bug fixes must be applied twice;
  currently the two copies are identical but will diverge.
  How:
  14. Create workspace/run_utils.py with the shared function
  15. Replace both copies with from run_utils import
  find_connector_json
  16. Update imports in matcher.py and offer_generator.py
  Files: workspace/matcher.py, workspace/offer_generator.py, new
  workspace/run_utils.py
  Done when: grep -r '_find_connector_json' workspace/ returns
  zero results; both scripts import from run_utils.
  Effort: S+

  ---
  [P1] Replace asyncio.get_event_loop() with
  asyncio.get_running_loop()

  What: Fix the deprecated event loop call in llm_router.py:515.
  Why: asyncio.get_event_loop() is deprecated in Python 3.10+ and
  raises DeprecationWarning in 3.12. The code runs inside a
  coroutine where get_running_loop() is both correct and explicit.
  How:
  17. Replace loop = asyncio.get_event_loop() with loop =
  asyncio.get_running_loop()
  Files: workspace/llm_router.py:515
  Done when: No DeprecationWarning on Python 3.12 when using
  Cerebras in async mode.
  Effort: XS+

  ---
  [P1] Replace print() bootstrap output in LLMRouter with
  logger.debug()

  What: Convert the 5 print() calls in _bootstrap_env() to
  logger.debug().
  Why: These fire at import time and pollute stdout for every
  process — API server, tests, pipeline scripts.
  How:
  18. Change print(f"[LLMRouter] ...") → logger.debug("[LLMRouter]
  ...") for all 5 lines
  19. Keep one logger.info for the "keys available" summary if
  desired
  Files: workspace/llm_router.py (lines 96–104)
  Done when: Importing llm_router produces no stdout output unless
   LOG_LEVEL=DEBUG.
  Effort: XS+

  ---
  [P1] Add path-guarded semaphore to client_finder.py HN comment
  fetch

  What: Limit concurrent HN API requests to a reasonable cap
  (e.g., 20).
  Why: The current code fires up to limit * 3 (default 150)
  simultaneous requests at hacker-news.firebaseio.com, which will
  trigger rate limiting or soft bans.
  How:
  20. Add sem = asyncio.Semaphore(20) before the gather
  21. Wrap each _fetch_comment call: async with sem: ...
  Files: workspace/client_finder.py:196
  Done when: --limit 50 run produces ≤20 concurrent connections
  (verifiable with httpx event hooks).
  Effort: XS+

  ---
  [P1] Fix SignalSource.JOBBOARDS misassignment in jobboards.py

  What: Reddit signals fetched in JobBoardsSignalMiner are tagged
  SignalSource.JOBBOARDS instead of SignalSource.REDDIT.
  Why: Downstream consumers filtering by source (e.g., analytics,
  debugging) get wrong provenance. The REDDIT enum value exists
  unused.
  How:
  22. In _fetch_reddit_signals, change
  source=SignalSource.JOBBOARDS → source=SignalSource.REDDIT on
  both PainSignal constructions (lines 123, 261)
  Files: Moneymaker/src/signal_miner/jobboards.py
  Done when: Signals from Reddit have source ==
  SignalSource.REDDIT; test_signal_miners.py passes.
  Effort: XS+

  ---
  [P1] Add sanitized report fields to run_pipeline.sh

  What: Write ideas_mined and ideas_passed_filter into the final
  report.json.
  Why: CLAUDE.md spec requires these fields; they are absent from
  the current report, breaking any consumer parsing the report
  schema.
  How:
  23. After STEP 1, capture the idea count: IDEAS_MINED=$(python -c
   "import json,sys;
  print(len(json.load(open('$BASE/ideas.json'))))")
  24. After STEP 2, capture passed count: IDEAS_PASSED=$(python -c
  "import json,sys;
  print(len(json.load(open('$BASE/connector.json'))))")
  25. Add both to the report.json heredoc
  Files: run_pipeline.sh
  Done when: cat workspace/runs/<id>/report.json includes
  ideas_mined and ideas_passed_filter integers.
  Effort: S+

  ---
  [P2] Package workspace/ as a proper Python package

  What: Add workspace/__init__.py and a minimal pyproject.toml so
  modules can be imported as from workspace.llm_router import
  router.
  Why: sys.path.insert(0, ...) appears in 4 files and is fragile —
   it depends on the caller's working directory and breaks IDE
  navigation.
  How:
  26. Create workspace/__init__.py (empty)
  27. Update all sys.path.insert consumers to use relative package
  imports or install the workspace package with pip install -e .
  Files: workspace/, Moneymaker/src/idea_generator.py,
  Moneymaker/src/money_filter.py, Moneymaker/src/mvp_builder.py,
  ai-knowledge-filler/akf.py
  Done when: All sys.path.insert blocks are removed; imports work
  from any working directory.
  Effort: M+
  ---
  [P2] Add tests for workspace scripts

  What: Write pytest tests for connector.py, matcher.py,
  offer_generator.py, and client_finder.py.
  Why: These are the critical glue scripts with zero test
  coverage. Bugs in connector.py silently zero-out the pipeline.
  How:
  28. Create workspace/tests/ with test_connector.py,
  test_matcher.py, test_offer_generator.py
  29. Use --dry-run fixtures (existing mock data in each script) to
   avoid API calls
  30. Cover: empty input, all-filtered output, atomic write,
  correct score thresholds
  Files: new workspace/tests/
  Done when: pytest workspace/tests/ passes with ≥ 80% line
  coverage on the three scripts.
  Effort: M+

  ---
  [P2] Add root CI workflow (Moneymaker + workspace)

  What: Create .github/workflows/ci.yml at the repo root covering
  Moneymaker and workspace tests.
  Why: Moneymaker/ has tests but no CI; failures are only
  discovered manually.
  How:
  31. Create .github/workflows/ci.yml with jobs for Moneymaker
  (pytest) and workspace (pytest, once tests exist)
  32. Run with --dry-run to avoid needing secrets in CI
  33. Add ruff lint step
  Files: .github/workflows/ci.yml (new)
  Done when: PRs to master trigger the workflow; a broken test
  fails the check.
  Effort: S+

  ---
  [P2] Pin all dependencies in root requirements.txt

  What: Add exact version pins to all 13 packages in
  requirements.txt.
  Why: Unpinned deps cause silent breakage when providers release
  breaking changes (e.g., pydantic v1→v2 breaking changes already
  affect the project).
  How:
  34. Run pip freeze in the current .venv and extract versions for
  the listed packages
  35. Update requirements.txt with package==x.y.z entries
  Files: requirements.txt
  Done when: pip install -r requirements.txt produces a
  deterministic environment.
  Effort: XS+

  ---
  [P2] Fix railway.toml / deployment config for ai-factory-api

  What: Add a proper requirements.txt or pyproject.toml inside
  ai-factory-api/ and complete railway.toml.
  Why: railway.toml is empty; Procfile references
  ai-factory-api.main:app but Railway won't know which
  dependencies to install.
  How:
  36. Create ai-factory-api/requirements.txt listing fastapi,
  uvicorn, pydantic
  37. Fill in railway.toml with [build] and [deploy] sections
  Files: railway.toml, new ai-factory-api/requirements.txt
  Done when: railway up or railway deploy completes without
  dependency errors.
  Effort: S+

  ---
  [P2] Remove leftover artifacts: test.md, package-lock.json

  What: Delete Moneymaker/test.md and the root package-lock.json
  (no package.json companion).
  Why: Dead files create confusion about what is intentional.
  How: git rm Moneymaker/test.md package-lock.json
  Files: Moneymaker/test.md, package-lock.json
  Done when: Both files are absent from the repo.
  Effort: XS+

  ---
  PHASE 3: ROADMAP

  Phase 1 — Stabilization (P0s first, unblock safe operation)
  ───────────────────────────────────────────────────────────
  [P0-1] Rotate Cerebras key, clean .env
  [P0-2] Fix path traversal in API run_id
  [P0-3] Add workspace/runs/, leads/ to .gitignore + untrack
  [P1-a] Fix Cerebras model mismatch        (depends on P0-1: key
  must be valid to test)
  [P1-b] Fix score threshold doc + log
  [P1-c] Replace asyncio.get_event_loop()
  [P1-d] Replace LLMRouter print() → logger
  [P1-e] Fix SignalSource.REDDIT tag

  Phase 2 — Architecture & Correctness (P1s)
  ────────────────────────────────────────────
  [P1-f] Extract _find_connector_json → run_utils.py   (no deps)
  [P1-g] Add semaphore to client_finder.py              (no deps)
  [P1-h] Add missing report.json fields to run_pipeline.sh
          └─ depends on workspace being tested first (nice to
  have)

  Phase 3 — Quality & Scale (P2s)
  ─────────────────────────────────
  [P2-a] Package workspace/ as Python package           (no deps)
          └─ blocks: P2-b (tests easier after packaging)
  [P2-b] Add tests for workspace scripts                (depends
  P2-a)
  [P2-c] Add root CI workflow                           (depends
  P2-b)
  [P2-d] Pin root requirements.txt                      (no deps)
  [P2-e] Fix railway.toml / api deployment config       (no deps)
  [P2-f] Remove dead files (test.md, package-lock.json) (no deps)

  Task dependencies:
  - P2-b (workspace tests) should come after P2-a (packaging) —
  importing is cleaner
  - P2-c (root CI) requires P2-b to have something to test
  - P1-a (model fix) is more confidently validated after P2-b
  tests exist

  ---
  Top 3 Highest-ROI Tasks

  Rank: 1
  Task: [P0] Fix path traversal in ai-factory-api
  Why: One-line sanitization that closes a real exploit on a
    deployed endpoint. Zero effort, immediate security gain.
  ────────────────────────────────────────
  Rank: 2
  Task: [P1] Fix Cerebras model mismatch
  Why: Silent quality regression — the "best" provider for
    generation has been running the smallest model the entire
  time.
     One-line fix restores intended output quality at no
  additional
     cost.
  ────────────────────────────────────────
  Rank: 3
  Task: [P0] Gitignore workspace/runs/
  Why: Stops generated data (scraped user content, LLM outputs)
    from accumulating in git history. Also keeps the repo lean —
    already 3 run directories tracked.