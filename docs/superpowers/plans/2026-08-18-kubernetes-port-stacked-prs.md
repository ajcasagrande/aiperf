# Kubernetes Port Stacked PRs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconstruct the monolithic Kubernetes-port commit as eight stacked branches, each independently mergeable, fully checked, and behaviorally equivalent at the stack tip.

**Architecture:** Preserve `ajc/k8s-clean-port` as the immutable source tree. Rebuild each branch from `origin/main` through its predecessor by transplanting only the ownership-defined files and diff hunks from the source commit. The dependency order in the approved specification is authoritative; boundaries are validated with import checks, complete repository checks, and tests on every branch.

**Tech Stack:** Git linked worktrees and patch staging; Python 3.11, uv, pytest/xdist, Ruff/pre-commit; Pydantic, Kubernetes AsyncIO, Kopf, Helm.

**Spec:** `docs/superpowers/specs/2026-08-18-kubernetes-port-stacked-prs-design.md`

## Global Constraints

- Source commit is `1286d559bc`; reconstruction base is `260d00f5e9` (`origin/main`).
- Preserve `ajc/k8s-clean-port`; never amend, reset, delete, or force-push it.
- Create only `ajc/k8s-runtime-contracts`, `ajc/k8s-api-contracts`, `ajc/k8s-pod-runtime`, `ajc/k8s-operator-core`, `ajc/k8s-cli`, `ajc/k8s-sweeps`, `ajc/k8s-dashboard`, and `ajc/k8s-delivery-docs`.
- Each branch's tree must be a strict prefix of the intended final feature; no compatibility shim that is absent from the source tree is allowed.
- Copy production changes only after first creating the focused tests from the source commit and observing the expected RED failure, except for generated/configuration-only artifacts.
- Every PR runs and passes: `pre-commit run --all-files`, `make validate-plugin-schemas`, `make test`, `make test-zmq`, `uv run pytest -m component_integration -n auto`, `uv run pytest -m integration -n auto`, and its focused suite. Run `uv run python tools/generate_crd.py --check` on branches containing CRD generation.
- After every full test gate, run the `aiperf-code-review` skill against that PR branch, inspect its living document and receipts, and resolve every confirmed or partially confirmed finding. A task review may begin only after the code-review result is clean; retain the review evidence in the SDD workspace or the branch's ignored `artifacts/` directory.
- Record the exact command, exit code, and commit SHA in the SDD ledger for every required gate. A failed environment-dependent command is not waived; diagnose and fix it or record a concrete external blocker.
- Before final handoff, verify the final delivery branch tree matches `1286d559bc` exactly, excluding only the planning/specification documents and intentional stack metadata commits.

---

### Task 1: Establish the reconstruction workspace and source inventory

**Files:**
- Create: `.superpowers/sdd/2026-08-18-kubernetes-port-stacked-prs/source-inventory.md` (ignored SDD artifact)
- Modify: no tracked implementation files
- Test: Git object/tree comparisons only

**Interfaces:**
- Consumes: source commit `1286d559bc`, base `260d00f5e9`, and the approved spec.
- Produces: an isolated linked worktree on `ajc/k8s-runtime-contracts`; a path-by-path inventory assigning every changed source file/hunk to one of Tasks 2-9.

- [ ] **Step 1: Create an isolated reconstruction worktree and verify its base**

Run:

```bash
git worktree add /tmp/aiperf-k8s-stack -b ajc/k8s-runtime-contracts 260d00f5e9
git -C /tmp/aiperf-k8s-stack rev-parse HEAD
```

Expected: the worktree HEAD is exactly `260d00f5e9`.

- [ ] **Step 2: Build the source inventory**

Generate the changed-file list with `git diff --name-status 260d00f5e9 1286d559bc`, assign each path to the eight PR ownership areas in the spec, and explicitly list every mixed file that needs `git add -p` partitioning.

- [ ] **Step 3: Verify the inventory is complete**

Compare the inventory's union to `git diff --name-only 260d00f5e9 1286d559bc`; the symmetric difference must be empty.

- [ ] **Step 4: Commit**

Do not make a tracked commit for this setup task. Record the worktree path, base SHA, and inventory verification in the SDD ledger.

### Task 2: Build PR 1, runtime and configuration contracts

**Files:**
- Modify: assigned `src/aiperf/common/**`, `src/aiperf/config/**`, plugin/runtime integration files, worker contract leaves, focused tests, and generated artifacts from the source inventory.
- Test: assigned `tests/unit/common/**`, `tests/unit/config/**`, property tests, and regression tests for local multiprocessing behavior.

**Interfaces:**
- Consumes: base runtime interfaces from `origin/main`.
- Produces: distributed-runtime-neutral contracts used by Kubernetes APIs and worker pod execution; branch `ajc/k8s-runtime-contracts`.

- [ ] **Step 1: Restore focused PR 1 tests and verify RED**

Apply only the assigned test hunks from `1286d559bc`, run their focused pytest selection, and confirm failure is due to missing runtime/config contract behavior.

- [ ] **Step 2: Restore the minimum production/configuration hunks for PR 1**

Use the inventory and patch staging. Include dynamic worker contract leaves required by `config.loader.helpers` and `common.subprocess_models`; exclude all Kubernetes API and operator behavior.

- [ ] **Step 3: Verify GREEN and generate owned artifacts**

Run the focused tests, generated plugin/schema artifacts when touched, and `make test-imports`.

- [ ] **Step 4: Run the complete mergeability gate**

Run every command in Global Constraints, then run a clean `aiperf-code-review` skill check, capture its document/receipt paths and outputs in the ledger, then commit with `feat(k8s): add runtime and configuration contracts`.

### Task 3: Build PR 2, Kubernetes API, CRD, and manifest contracts

**Files:**
- Modify: assigned `src/aiperf/kubernetes/**`, CRD model/config conversion files, `tools/generate_crd.py`, generated CRDs, and contract tests.
- Test: assigned Kubernetes schema/client/validation/CRD-generator tests.

**Interfaces:**
- Consumes: PR 1 runtime/config contracts.
- Produces: typed Kubernetes resources, client lifecycle, workload schemas, validation, manifest construction, and CRD artifacts for later PRs.

- [ ] **Step 1: Create branch `ajc/k8s-api-contracts` from PR 1 and restore focused tests**

Confirm the restored schema/client tests fail because the Kubernetes contract is absent.

- [ ] **Step 2: Restore Kubernetes contract production hunks**

Include async client closure, CR references/models, AIPerfJob/AIPerfSweep validation, spec conversion, serialized-run/results-sidecar contracts, resources/templates, and the CRD generator. Exclude kopf, worker pod orchestration, CLI, and dashboard code.

- [ ] **Step 3: Regenerate and verify artifacts**

Run `uv run python tools/generate_crd.py`, then `uv run python tools/generate_crd.py --check`, plus focused tests and import checks.

- [ ] **Step 4: Run the complete mergeability gate and commit**

Run a clean `aiperf-code-review` skill check after all Global Constraint gates pass; commit with `feat(k8s): add Kubernetes workload contracts` only after its confirmed findings are resolved.

### Task 4: Build PR 3, Kubernetes pod execution

**Files:**
- Modify: assigned controller Kubernetes manager/monitoring files, worker group/pod lifecycle files, runtime wiring, and focused tests.
- Test: assigned `tests/unit/controller/**`, `tests/unit/workers/**`, records/finalization tests.

**Interfaces:**
- Consumes: PR 1 runtime contracts and PR 2 Kubernetes contracts.
- Produces: Kubernetes service selection and pod-local worker execution without a kopf operator.

- [ ] **Step 1: Create `ajc/k8s-pod-runtime` from PR 2 and restore focused tests for RED**

Verify tests fail on absent Kubernetes service management or worker-pod lifecycle behavior.

- [ ] **Step 2: Restore pod execution hunks**

Include KubernetesServiceManager, SystemController routing, WorkerGroupManager/group coordination, dataset/tokenizer download, upload/finalization, and clock synchronization. Do not include operator handlers or CLI commands.

- [ ] **Step 3: Verify focused GREEN behavior**

Run controller/worker/records focused suites and `make test-imports`.

- [ ] **Step 4: Run the complete mergeability gate and commit**

Run a clean `aiperf-code-review` skill check after the full gate and commit with `feat(k8s): run AIPerf services in worker pods` only after review findings are resolved.

### Task 5: Build PR 4, job operator and results API

**Files:**
- Modify: assigned `src/aiperf/operator/**`, job-centric API/router files, operator tests, and job/operator documentation.
- Test: assigned `tests/unit/operator/**` excluding sweep-specific modules and assigned component tests.

**Interfaces:**
- Consumes: Kubernetes CRD/API contracts and pod execution runtime.
- Produces: a kopf-reconciled AIPerfJob, durable lifecycle/status/results storage, and the job-centric results API.

- [ ] **Step 1: Create `ajc/k8s-operator-core` from PR 3 and restore job-focused tests for RED**

Confirm failures identify absent handler/status/results behavior rather than missing sweep functionality.

- [ ] **Step 2: Restore job-only operator/API hunks**

Include entrypoint, environment, metrics, cache, create/monitor/lifecycle/cleanup/completion/restart/JobSet-terminal handlers, status/progress/results/index/archive, and job-centric FastAPI routes. Exclude sweep handlers/routes and static dashboard assets.

- [ ] **Step 3: Verify focused GREEN behavior**

Run job operator, result-server, and component-integration focused suites; verify imports and SQLite disk-fallback behavior.

- [ ] **Step 4: Run the complete mergeability gate and commit**

Run a clean `aiperf-code-review` skill check after the full gate and commit with `feat(k8s): add AIPerfJob operator and results API` only after review findings are resolved.

### Task 6: Build PR 5, job-centric Kubernetes CLI

**Files:**
- Modify: assigned `src/aiperf/cli_commands/kube/**`, CLI registration/config options, CLI tests, generated CLI/env documentation, and job-centric Kubernetes guides.
- Test: assigned CLI command tests.

**Interfaces:**
- Consumes: PR 2 API contracts and PR 4 operator results API.
- Produces: complete AIPerfJob CLI workflows with text/JSON output.

- [ ] **Step 1: Create `ajc/k8s-cli` from PR 4 and restore job CLI tests for RED**

Verify the command registration and job command behavior are absent before implementation.

- [ ] **Step 2: Restore job CLI hunks**

Include app registration, shared options, init/generate/validate/preflight/setup/deploy/profile/logs/attach/results/debug/list/show/delete/cancel/cleanup/dashboard/proxy/shutdown only where job-centric. Leave sweep command and sweep selectors for Task 7.

- [ ] **Step 3: Generate and verify CLI artifacts**

Run `make generate-all-docs`, focused CLI tests, JSON-output tests, and import checks.

- [ ] **Step 4: Run the complete mergeability gate and commit**

Run a clean `aiperf-code-review` skill check after the full gate and commit with `feat(k8s): add AIPerfJob Kubernetes CLI` only after review findings are resolved.

### Task 7: Build PR 6, sweep orchestration

**Files:**
- Modify: assigned `src/aiperf/sweep_controller/**`, operator sweep handlers/routes/models, sweep CLI behavior, sweep tests, and sweep documentation.
- Test: assigned sweep-controller, operator sweep, and CLI sweep tests.

**Interfaces:**
- Consumes: operator environment/results API and Kubernetes workload contracts.
- Produces: UID/epoch-fenced AIPerfSweep child-job orchestration, aggregation, archive, and CLI/API visibility.

- [ ] **Step 1: Create `ajc/k8s-sweeps` from PR 5 and restore sweep tests for RED**

Confirm red failures cover child creation/naming, parent rollup, cancellation, aggregation, and restart behavior.

- [ ] **Step 2: Restore sweep production hunks**

Include sweep-controller execution and status, operator sweep handlers/aggregate fetch/results routes, sweep selectors/CLI, and model/validation extensions. Preserve parent UID and epoch fencing on all child-facing paths.

- [ ] **Step 3: Verify focused GREEN behavior**

Run sweep-controller and operator sweep suites, plus focused CLI tests and generated CRD check if models changed.

- [ ] **Step 4: Run the complete mergeability gate and commit**

Run a clean `aiperf-code-review` skill check after the full gate and commit with `feat(k8s): add cluster sweep orchestration` only after review findings are resolved.

### Task 8: Build PR 7, dashboard

**Files:**
- Modify: assigned API dependencies/models/websocket/static routes, `src/aiperf/api/static-v2/**`, dashboard server/assets, UI tests, and dashboard docs.
- Test: assigned operator UI and dashboard tests.

**Interfaces:**
- Consumes: stable job and sweep API surfaces.
- Produces: browser dashboard for live and archived job/sweep state without shared operator-process state.

- [ ] **Step 1: Create `ajc/k8s-dashboard` from PR 6 and restore dashboard tests for RED**

Verify failures cover absent transport, server/static assets, or rendering behavior.

- [ ] **Step 2: Restore dashboard/API hunks**

Include dependency injection, WebSocket/pod state, static serving, dashboard server, static-v2 assets, and tests. Do not pull Helm/CI delivery wiring forward.

- [ ] **Step 3: Verify focused GREEN behavior**

Run dashboard/server/router/accessibility suites and static UI harness tests.

- [ ] **Step 4: Run the complete mergeability gate and commit**

Run a clean `aiperf-code-review` skill check after the full gate and commit with `feat(k8s): add operator dashboard` only after review findings are resolved.

### Task 9: Build PR 8, delivery and final equivalence audit

**Files:**
- Modify: assigned Helm chart, Dockerfile, Makefile, package metadata/lockfile/attributions, CI workflows, dev fixtures, integration/chaos/audit tests, and remaining deployment documentation.
- Test: Helm/chart checks plus complete repository and Kubernetes suites.

**Interfaces:**
- Consumes: the complete functional stack.
- Produces: deployable chart/image/CI configuration and a final tree equivalent to the source feature.

- [ ] **Step 1: Create `ajc/k8s-delivery-docs` from PR 7 and restore delivery tests/artifacts for RED where applicable**

Verify missing chart/CI/build behavior with the project checks that own it.

- [ ] **Step 2: Restore delivery hunks and generated artifacts**

Include Helm templates/values/schema, Dockerfile/Makefile/package/lock/attribution changes, workflows, dev fixtures, integration/chaos/audit tests, and remaining deployment documentation.

- [ ] **Step 3: Verify delivery behavior**

Run Helm lint/template/chart consistency, CRD generation check, image build, and all focused integration/chaos/audit suites.

- [ ] **Step 4: Run the complete mergeability gate, commit, and prove final equivalence**

Run a clean `aiperf-code-review` skill check after the full gate. Commit with `feat(k8s): package Kubernetes operator deployment`. Compare `git diff --name-status 1286d559bc HEAD` and `git diff --quiet 1286d559bc HEAD -- . ':(exclude)docs/superpowers/**'`; both must demonstrate no implementation-tree divergence. Record the exact proof and code-review evidence in the ledger.
