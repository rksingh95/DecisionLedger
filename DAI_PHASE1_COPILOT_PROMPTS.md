# DecisionLedger — Phase 1 Build Prompts
# Authority, Policy Versioning, Override Modelling & Decision Intelligence
# GitHub Copilot Context Windows · Solo Founder Edition

---

## ══════════════════════════════════════════════════════════════
## PHASE 0 AUDIT — What was built vs what was specified
## Read this before starting Phase 1
## ══════════════════════════════════════════════════════════════

### ✅ PHASE 0: FULLY DELIVERED

Based on the README and roadmap completion markers, Phase 0 delivered:

| Component | Status | Notes |
|---|---|---|
| Python SDK (fluent builder) | ✅ Done | All 4 patterns implemented |
| Context manager (auto-commit on exception) | ✅ Done | |
| @log_decision decorator | ✅ Done | |
| LangChain callback handler | ✅ Done | |
| OpenTelemetry span bridge | ✅ Done | Pattern 5 added beyond spec |
| SHA-256 hash chain engine | ✅ Done | |
| FastAPI server | ✅ Done | |
| PostgreSQL append-only storage | ✅ Done | |
| SQLite local dev backend | ✅ Done | |
| Docker Compose one-command deploy | ✅ Done | |
| Alembic migrations | ✅ Done | |
| EU AI Act Article 19 export (JSON + Text) | ✅ Done | |
| PDF compliance report | ✅ Done | Beyond original spec — excellent |
| CLI (verify, query, export, status) | ✅ Done | |
| Prometheus metrics endpoint | ✅ Done | Beyond spec — excellent |
| CI/CD GitHub Actions pipeline | ✅ Done | |
| Pre-commit hooks | ✅ Done | |
| 94% test coverage | ✅ Done | Exceeds 90% target |
| PyPI package published | ✅ Done | decision-ledger-sdk |

### ⚠️ PHASE 0 GAPS — Must fix before Phase 1 build starts

These are missing from the Phase 0 spec that will block Phase 1 if not resolved:

**GAP 1 — No policy store exists**
Phase 0 records `policy_id` and `policy_version` as strings only. There is
no PolicyVersion entity, no policy content storage, no policy lifecycle
management. Phase 1 requires this as foundational infrastructure.
→ Fix: Build PolicyVersion store in Phase 1 Prompt 01 BEFORE anything else.

**GAP 2 — Authority chain is flat, not hierarchical**
`delegation_source` is a single string field. A real authority chain is:
Board → CRO → Underwriting Team → Agent. This lineage is unmodelled.
Phase 1 decision intelligence requires traversable authority trees.
→ Fix: AuthorityChain model in Phase 1 Prompt 02.

**GAP 3 — No decision replay capability**
Records are stored but there is no mechanism to re-execute a decision
with different inputs (different model, different policy version) and
diff the outcome. This was identified as the strongest wedge in the
original product analysis and remains unbuilt.
→ Fix: DecisionReplay engine in Phase 1 Prompt 06.

**GAP 4 — Exception reason_code is unvalidated**
`exception_reason_code` is stored as a free string. This violates the
"no free text in core schema" principle. It should be an enum registry
per decision_type.
→ Fix: ExceptionReasonRegistry in Phase 1 Prompt 03.

**GAP 5 — No multi-tenant isolation**
Currently a single API key grants access to all decisions across all
agents. Enterprises need workspace-level isolation: Org → Workspace →
Agent. Without this, no enterprise will share an instance.
→ Fix: Workspace + API key scoping in Phase 1 Prompt 08.

**GAP 6 — No decision lineage (parent-child relationships)**
Agents make chains of decisions. D2 is made because of D1. This causal
lineage is unmodelled. The `parent_decision_id` field was in the original
spec but does not appear in the Phase 0 schema.
→ Fix: DecisionLineage graph in Phase 1 Prompt 05.

**GAP 7 — Article 12 logging not fully addressed**
Article 12 (record-keeping, distinct from Article 19) requires automatic
logging of system events to facilitate risk identification and post-market
monitoring. The current export covers Article 19 (automatically generated
logs) but not Article 12's post-market monitoring requirements.
→ Fix: PostMarketMonitoringReport in Phase 1 Prompt 09.

---

# DecisionLedger — Phase 0.1 + Phase 1 Build Prompts

# Primitive Hardening Before Decision Intelligence

# GitHub Copilot / Antigravity Context Windows · Solo Founder Edition

---

## ══════════════════════════════════════════════════════════════

## PHASE 0.1 MANDATORY GATE — COMPLETE BEFORE PHASE 1

## Primitive Hardening (Not Optional)

## ══════════════════════════════════════════════════════════════

Before any Policy Intelligence, Replay, Drift Detection or Multi-Tenant work:

**The primitive must be hardened.**

Phase 1 assumes these invariants exist.

Without them, everything above them is structurally wrong.

---

## Missing Primitive Gaps To Close

| Gap                                 | Status    | Must Fix |
| ----------------------------------- | --------- | -------- |
| Hierarchical Authority Chain        | ❌ Missing | P0.1-01  |
| Explicit Failure Mode Records       | ❌ Missing | P0.1-02  |
| Duplicate / Replay Attack Detection | ❌ Missing | P0.1-03  |
| Chain Break Localization            | ❌ Missing | P0.1-03  |
| Canonical Hash Input Hardening      | ❌ Missing | P0.1-03  |
| Failure Mode Documentation          | ❌ Missing | P0.1-04  |
| “Why Not Logs?” Category Framing    | ❌ Missing | P0.1-05  |

All required.

---

## GLOBAL CONTEXT ADDITION

Add to global principles:

13. Authority is first-class, not metadata.
14. Failures are decision events.
15. Integrity verification must identify corruption location, not just pass/fail.
16. Duplicate/replay attacks must be detectable.
17. Canonical hashing must be deterministic across environments.

---

## ══════════════════════════════════════════════════════════════

## PROMPT P0.1-01 — Explicit Authority Chain Hardening

## ══════════════════════════════════════════════════════════════

TASK:
Extend Phase 0 decision schema and SDK.

Do NOT use flat delegation strings anymore.

Build:

```text
dai/authority/
  delegation.py
  models.py
```

Add:

```python
class DelegationNode(BaseModel):
    authority_id: str
    authority_type: Literal[
        "POLICY_BOARD",
        "RISK_COMMITTEE",
        "SYSTEM",
        "HUMAN_ROLE"
    ]
    policy_reference: Optional[str]
    delegated_at: datetime
```

Decision schema addition:

```python
delegation_chain: list[DelegationNode]
```

SDK:

```python
.with_delegation_chain(...)
```

Validation:

* chain length >=1
* preserve order
* immutable after commit

Store inside record JSONB.

Not separate mutable table.

Tests:

* valid chain passes
* empty chain rejected
* order preserved
* mutation after commit rejected

---

## Acceptance:

Every decision must now answer:

Who delegated authority to whom?

Not merely “what team owned it.”

---

## ══════════════════════════════════════════════════════════════

## PROMPT P0.1-02 — Failure Mode Records

## ══════════════════════════════════════════════════════════════

TASK:
Model failures as first-class decision events.

Create:

```python
class FailureMode(BaseModel):
    type: Literal[
      "NETWORK_FAILURE",
      "SIGNAL_DEGRADATION",
      "POLICY_MISSING",
      "COMMIT_RETRY",
      "CONSERVATIVE_FALLBACK"
    ]
    recoverable: bool
    fallback_applied: bool
```

Decision schema:

```python
failure_mode: Optional[FailureMode]
```

SDK:

```python
.with_failure_mode(...)
```

Context manager exceptions:
Must commit failure-state decision record.

Never silently lose failed decisions.

Tests:

* exception produces record
* fallback recorded
* retries preserved

---

## Principle

Failure itself is a consequential decision.

Record it.

---

## ══════════════════════════════════════════════════════════════

## PROMPT P0.1-03 — Integrity Hardening

## ══════════════════════════════════════════════════════════════

TASK:
Strengthen hash-chain verification.

Implement:

### A. Canonical serialization

* sorted keys
* normalized timestamps
* deterministic serializer

Hash rule:

```text
SHA256(previous_hash + canonical_json(record))
```

---

### B. Chain break localization

Verify should return:

```python
class ChainVerifyResult(BaseModel):
   valid: bool
   first_broken_decision_id: Optional[str]
   expected_previous_hash: Optional[str]
   actual_previous_hash: Optional[str]
```

Not boolean only.

---

### C. Duplicate / replay detection

Reject:

* duplicate decision_id
* replayed historical record

Add DB uniqueness + tests.

---

Tests:

* tamper detected
* break localized
* duplicates rejected
* canonical hash deterministic

---

## ══════════════════════════════════════════════════════════════

## PROMPT P0.1-04 — Failure Mode Documentation

## ══════════════════════════════════════════════════════════════

Create:

```text
docs/failure_modes.md
```

Document:

* server unavailable
* hash mismatch
* commit timeout
* duplicate replay attack
* missing authority
* conservative fallback path

For each:

* system behavior
* retries
* operator response

---

## ══════════════════════════════════════════════════════════════

## PROMPT P0.1-05 — “Why Not Logs?” Category Definition

## ══════════════════════════════════════════════════════════════

Add README section:

| Standard Logs            | DecisionLedger               |
| ------------------------ | ---------------------------- |
| Unstructured events      | Typed decision records       |
| API traces               | Authority + policy + outcome |
| Difficult to reconstruct | Replayable                   |
| Weak audit evidence      | Hash-linked evidence         |

Mandatory.

This is category formation.

---

## ══════════════════════════════════════════════════════════════

## PHASE 0.1 VERIFICATION GATE

## Must pass before Phase 1 begins

## ══════════════════════════════════════════════════════════════

Run:

```bash
pytest tests/unit/test_authority_chain.py
pytest tests/unit/test_failure_modes.py
pytest tests/unit/test_chain_integrity.py

dai verify --from 2026-01-01 --to 2026-12-31
```

Must prove:

* Authority chain valid
* Failures persisted
* Duplicates rejected
* Chain break localization works
* Canonical hashes deterministic

Only then start P1-01.

---

## ══════════════════════════════════════════════════════════════

## PHASE 1 EXECUTION ORDER (REVISED)

## ══════════════════════════════════════════════════════════════

Revised order:

| #       | Prompt                | Type           |
| ------- | --------------------- | -------------- |
| P0.1-01 | Authority Hardening   | Mandatory Gate |
| P0.1-02 | Failure Modes         | Mandatory Gate |
| P0.1-03 | Integrity Hardening   | Mandatory Gate |
| P0.1-04 | Failure Documentation | Mandatory Gate |
| P0.1-05 | Category Framing      | Mandatory Gate |
| P1-01   | Policy Version Store  | Phase 1        |
| P1-02   | Authority Chain Model | Phase 1        |
| P1-03   | Decision Lineage      | Phase 1        |
| P1-04   | Replay Engine         | Phase 1        |
| P1-05   | Drift Detection       | Phase 1        |
| P1-06   | Workspace RBAC        | Phase 1        |
| P1-07   | Article 12 Monitoring | Phase 1        |
| P1-08   | Retention Controls    | Phase 1        |
| P1-09   | CLI Extensions        | Phase 1        |
| P1-10   | Integration Tests     | Phase 1        |
| P1-11   | Documentation         | Phase 1        |

---

## Critical Rule

Do not let Antigravity skip P0.1 and jump to intelligence.

If the primitive is weak,
intelligence features become product theater.

Infrastructure first.
Always.


## ══════════════════════════════════════════════════════════════
## GLOBAL CONTEXT — PASTE THIS FIRST IN EVERY PHASE 1 SESSION
## ══════════════════════════════════════════════════════════════

```
PRODUCT: DecisionLedger SDK — Decision Authority Infrastructure
PHASE: 1 — Authority, Policy Versioning & Decision Intelligence
PACKAGE: decision-ledger-sdk (PyPI published)
IMPORT: import dai
PYTHON: 3.13+
REPO: github.com/rksingh95/DecisionLedger

WHAT ALREADY EXISTS (Phase 0 — do not rebuild):
- dai/ — full SDK with builder, context manager, decorator, LangChain,
  OpenTelemetry integrations
- dai_server/ — FastAPI server with ingest, query, verify, export routes
- PostgreSQL append-only storage with SHA-256 hash chain
- Docker Compose full stack deployment
- EU AI Act Article 19 export (JSON + PDF + text)
- CLI: dai verify, dai query, dai export, dai status
- 94% test coverage, CI/CD pipeline, pre-commit hooks
- Published to PyPI as decision-ledger-sdk

PHASE 1 GOAL:
Transform the ledger from a passive recording system into an active
authority and intelligence layer. Three pillars:

PILLAR A — POLICY AUTHORITY:
  Policy versioning, policy store, policy diff, authority chains,
  structured exception modelling with typed reason registries.
  Regulatory basis: EU AI Act Articles 9, 13, 17.

PILLAR B — DECISION INTELLIGENCE:
  Decision lineage (parent-child graphs), decision replay and diff,
  policy drift detection, override clustering, cross-agent consistency.
  Regulatory basis: EU AI Act Articles 9, 12, 14.

PILLAR C — GOVERNANCE HARDENING:
  Multi-tenant workspace isolation, role-based access control,
  post-market monitoring reports (Article 12), data retention controls,
  tamper-evident audit package for regulators.
  Regulatory basis: EU AI Act Articles 12, 17, 18, 20.

PHASE 1 REGULATORY CONTEXT (critical for design decisions):
- EU AI Act Article 9: Risk management system — continuous, documented,
  covering full AI lifecycle. Requires policy change tracking.
- EU AI Act Article 12: Record-keeping for post-market monitoring,
  not just decision logs — event patterns, anomalies, drift.
- EU AI Act Article 13: Transparency to deployers — decision rationale
  must be interpretable by qualified humans.
- EU AI Act Article 14: Human oversight — system must support
  designated humans to intervene. Override recording is legal evidence.
- EU AI Act Article 17: Quality management system — documented
  processes for monitoring, corrective actions, policy governance.
- EU AI Act Article 20: Corrective actions — providers must act when
  systems don't comply with the Act.
- Full high-risk obligations binding from 2 August 2026.

CORE DESIGN PRINCIPLES (unchanged from Phase 0):
1. Append-only. No UPDATE, no DELETE on decision records.
2. Hash-chained. SHA-256 integrity on every record.
3. Typed. No free text in schema. Enums, refs, codes only.
4. Non-blocking. SDK failure never crashes the agent.
5. Framework-agnostic. Works with any Python agent.
6. Self-hostable. Full stack via docker compose up.
7. EU AI Act compliant by design.

NEW PRINCIPLES FOR PHASE 1:
8. Policy-bound. Every decision references a versioned, stored policy.
9. Authority-explicit. Delegation chains are structured, not strings.
10. Lineage-aware. Decisions know their causal predecessors.
11. Workspace-isolated. Multi-tenant by design from day one.
12. Drift-observable. Policy and behaviour changes are surfaced, not hidden.

TECH STACK (additions for Phase 1):
All Phase 0 stack, plus:
- networkx >= 3.3 (decision lineage graphs)
- deepdiff >= 7.0 (policy diff + decision outcome diff)
- pandas >= 2.2 (drift detection analytics)
- apscheduler >= 3.10 (scheduled drift detection jobs)
- jinja2 >= 3.1 (report templating for Article 12 monitoring reports)
- passlib + python-jose (RBAC token management)

REPOSITORY STRUCTURE — NEW ADDITIONS FOR PHASE 1:
dai/
  policy/
    __init__.py
    store.py           # PolicyVersion CRUD + diff
    models.py          # PolicyVersion, PolicyDiff Pydantic models
    registry.py        # ExceptionReasonRegistry per decision_type
  authority/
    __init__.py
    chain.py           # AuthorityChain builder + validator
    models.py          # AuthorityNode, DelegationChain models
  lineage/
    __init__.py
    graph.py           # DecisionLineage directed graph
    models.py          # LineageNode, LineageEdge models
  replay/
    __init__.py
    engine.py          # DecisionReplay + DecisionDiff
    models.py          # ReplayRequest, ReplayResult, DecisionDiff
  intelligence/
    __init__.py
    drift.py           # PolicyDriftDetector
    overrides.py       # OverrideClusterAnalyser
    consistency.py     # CrossAgentConsistencyChecker
dai_server/
  routes/
    policy.py          # /policies CRUD routes
    authority.py       # /authority-chains routes
    lineage.py         # /decisions/{id}/lineage routes
    replay.py          # /decisions/{id}/replay routes
    intelligence.py    # /intelligence/* routes
    workspaces.py      # /workspaces CRUD + API key management
  db/
    models.py          # Extended with PolicyVersionORM, WorkspaceORM, etc.
    migrations/        # New Alembic migrations
  monitoring/
    article12.py       # Post-market monitoring report generator
    scheduler.py       # Scheduled drift detection jobs
```

---

## ══════════════════════════════════════════════════════════════
## PROMPT P1-01 — Policy Version Store
## ══════════════════════════════════════════════════════════════

**Session goal:** Build the policy management infrastructure. This is the foundation for everything else in Phase 1. Without a policy store, policy versioning in decision records is just a string.

```
[PASTE GLOBAL CONTEXT ABOVE FIRST]

TASK: Build dai/policy/models.py, dai/policy/store.py, dai/policy/registry.py,
      and dai_server/routes/policy.py.

═══ dai/policy/models.py ═══

1. ENUM: PolicyStatus
   draft | active | deprecated | superseded

2. ENUM: PolicyChangeType
   new_version | amendment | emergency_amendment | deprecation | supersession

3. DATACLASS: PolicyClause
   clause_id: str (e.g. "3.1", "4.2")
   title: str
   content_hash: str (SHA-256 of clause text — no raw text stored)
   effective_from: datetime
   mandatory: bool

4. PYDANTIC MODEL: PolicyVersion
   policy_id: str
   version: str (semver)
   status: PolicyStatus
   title: str
   description: str
   effective_from: datetime
   effective_to: Optional[datetime]
   supersedes_version: Optional[str] (previous version this replaces)
   change_type: PolicyChangeType
   change_summary: str (max 500 chars — not free text, structured summary)
   clauses: list[PolicyClause]
   authorized_decision_types: list[str] (which decision_types this policy governs)
   max_auto_approve_confidence: float (below this, human oversight required)
   exception_types_allowed: list[str] (which ExceptionTypes are permitted)
   retention_period_days: int (legal retention requirement)
   policy_hash: str (SHA-256 of entire policy content for tamper evidence)
   created_at: datetime
   created_by: str (role/system that created this version)
   workspace_id: str

   Model config: frozen=True (immutable after creation)

   Validator: effective_to must be after effective_from if set.
   Validator: version must be valid semver.
   Validator: max_auto_approve_confidence must be 0.0-1.0.

5. PYDANTIC MODEL: PolicyDiff
   policy_id: str
   from_version: str
   to_version: str
   diffed_at: datetime
   clauses_added: list[str] (clause_ids)
   clauses_removed: list[str]
   clauses_modified: list[str]
   threshold_changed: bool
   max_auto_approve_confidence_delta: Optional[float]
   exception_types_added: list[str]
   exception_types_removed: list[str]
   risk_level_change: Literal["increased", "decreased", "unchanged"]
   summary: str

6. PYDANTIC MODEL: PolicyVersionCreate
   Same as PolicyVersion minus: policy_hash, created_at (server-set).

7. PYDANTIC MODEL: PolicyResolveRequest
   policy_id: str
   at_timestamp: datetime (resolve which version was active at this moment)
   workspace_id: str

═══ dai/policy/store.py ═══

CLASS: PolicyStore
Manages PolicyVersion lifecycle. Uses the same DB session as dai_server.
All methods are async.

Methods:

async create_version(create: PolicyVersionCreate) -> PolicyVersion
  - Validate no version string collision for this policy_id
  - If a current ACTIVE version exists: set its status to SUPERSEDED,
    set effective_to = create.effective_from
  - Compute policy_hash = SHA-256(policy_id + version + clauses_content)
  - INSERT new PolicyVersionORM record
  - Return PolicyVersion

async get_version(policy_id: str, version: str, workspace_id: str) -> PolicyVersion
  - Fetch by policy_id + version + workspace_id
  - Raise PolicyNotFoundError if missing

async resolve_at(request: PolicyResolveRequest) -> PolicyVersion
  CRITICAL METHOD — used when reconstructing historical decisions.
  "Which policy version was ACTIVE for policy_id at timestamp T?"
  Query: SELECT * FROM policy_versions
         WHERE policy_id = ? AND workspace_id = ?
           AND effective_from <= T
           AND (effective_to IS NULL OR effective_to > T)
           AND status IN ('active', 'superseded')
         ORDER BY effective_from DESC LIMIT 1
  If none found: raise PolicyNotFoundAtTimestampError(policy_id, timestamp)

async diff_versions(
    policy_id: str,
    from_version: str,
    to_version: str,
    workspace_id: str,
) -> PolicyDiff
  Fetch both versions. Use deepdiff to compare clause content_hashes,
  thresholds, exception_types_allowed. Build and return PolicyDiff.

async list_versions(policy_id: str, workspace_id: str) -> list[PolicyVersion]
  All versions ordered by effective_from DESC.

async deprecate(policy_id: str, version: str, workspace_id: str) -> PolicyVersion
  Set status=deprecated, effective_to=now().

═══ dai/policy/registry.py ═══

CLASS: ExceptionReasonRegistry
Manages decision_type-specific exception reason code enums.
Prevents free-text exception reasons.

Concept: each decision_type registers its valid exception reason codes.
When a decision commits with exception_applied=True, the reason_code
is validated against this registry for the decision_type.

Methods:

register(decision_type: str, reason_codes: list[str]) -> None
  Register valid reason codes for a decision_type.
  Example:
    registry.register("claims_triage", [
        "insufficient_evidence",
        "fraud_suspicion",
        "policy_ambiguity",
        "threshold_breach",
        "manual_escalation_required",
    ])

validate(decision_type: str, reason_code: str) -> bool
  Returns True if reason_code is registered for decision_type.
  Raises UnregisteredReasonCodeError if not found.

get_codes(decision_type: str) -> list[str]
  Returns all registered codes for decision_type.

list_all() -> dict[str, list[str]]
  Returns full registry.

MODULE LEVEL: default_registry = ExceptionReasonRegistry()
Pre-populate with common codes for standard decision types:
  "claims_triage": ["insufficient_evidence", "fraud_suspicion",
                    "policy_ambiguity", "threshold_breach",
                    "manual_escalation_required", "duplicate_claim"]
  "risk_classification": ["data_quality_issue", "model_uncertainty",
                          "regulatory_constraint", "edge_case",
                          "conflicting_signals"]
  "credit_decision": ["manual_review_required", "regulatory_hold",
                      "incomplete_application", "fraud_flag"]

═══ dai_server/routes/policy.py ═══

Router prefix: /policies

POST /policies
  Body: PolicyVersionCreate
  Response: PolicyVersion (201)
  Creates new policy version. Sets workspace from API key context.

GET /policies/{policy_id}
  Response: list[PolicyVersion] (all versions for this policy)

GET /policies/{policy_id}/{version}
  Response: PolicyVersion

GET /policies/{policy_id}/resolve?at={timestamp}
  Response: PolicyVersion (version active at that timestamp)
  This endpoint is used by the decision replay engine.

GET /policies/{policy_id}/diff?from={version}&to={version}
  Response: PolicyDiff

POST /policies/{policy_id}/{version}/deprecate
  Response: PolicyVersion (updated)

GET /policies/registry/exception-codes
  Response: dict[str, list[str]] (full reason code registry)

POST /policies/registry/exception-codes
  Body: {"decision_type": str, "reason_codes": list[str]}
  Register custom exception codes for a decision_type.

═══ SQLAlchemy model: PolicyVersionORM ═══

Table: policy_versions
Columns:
  policy_id: String(255), not null, indexed
  version: String(50), not null
  workspace_id: String(36), not null, indexed
  status: String(50), not null, indexed
  title: String(500), not null
  description: Text, not null
  effective_from: DateTime(timezone=True), not null, indexed
  effective_to: DateTime(timezone=True), nullable, indexed
  change_type: String(100), not null
  change_summary: String(500), not null
  authorized_decision_types: Text (JSON array stored as text)
  max_auto_approve_confidence: Float, not null
  exception_types_allowed: Text (JSON array)
  retention_period_days: Integer, not null, default=180
  policy_hash: String(64), not null, unique
  clauses_json: Text (full clauses as JSON)
  created_at: DateTime(timezone=True), not null
  created_by: String(255), not null
  full_record_json: Text, not null

Primary key: (policy_id, version, workspace_id)
Indexes:
  (policy_id, workspace_id, effective_from) — for resolve_at queries
  (policy_id, workspace_id, status) — for active policy lookups

Append-only: add same NO UPDATE/DELETE rules as decisions table.

═══ Write tests: tests/unit/test_policy_store.py ═══
- create_version: success, version collision error
- resolve_at: active version found, superseded version found, nothing found
- diff_versions: clauses added/removed detected correctly
- deprecate: status updated, effective_to set
- ExceptionReasonRegistry: register, validate pass, validate fail (UnregisteredReasonCodeError)
```

---

## ══════════════════════════════════════════════════════════════
## PROMPT P1-02 — Authority Chain Model
## ══════════════════════════════════════════════════════════════

**Session goal:** Replace the flat `delegation_source` string with a proper hierarchical authority chain that can be traversed, validated, and audited.

```
[PASTE GLOBAL CONTEXT ABOVE FIRST]

TASK: Build dai/authority/models.py, dai/authority/chain.py,
      dai_server/routes/authority.py.

═══ dai/authority/models.py ═══

1. ENUM: AuthorityNodeType
   human_role | system | team | policy_body | regulator | automated_agent

2. ENUM: DelegationType
   explicit | implicit | emergency | standing | time_limited

3. PYDANTIC MODEL: AuthorityNode
   node_id: str (unique within chain)
   node_type: AuthorityNodeType
   name: str (e.g. "Chief Risk Officer", "underwriting-agent-v2")
   role: str (formal role title or system identifier)
   delegation_type: DelegationType
   delegated_at: Optional[datetime]
   delegation_expires_at: Optional[datetime]
   can_override: bool (can this node override automated decisions?)
   max_decision_value: Optional[float] (e.g. max claim value they can approve)
   constraints: dict[str, str] (key/value constraints, string values only)

4. PYDANTIC MODEL: AuthorityChain
   chain_id: str (UUIDv7, generated)
   workspace_id: str
   decision_type: str
   nodes: list[AuthorityNode] (ordered: highest → lowest authority)
   effective_from: datetime
   effective_to: Optional[datetime]
   chain_hash: str (SHA-256 of all node IDs + delegation types in order)
   created_at: datetime

   Property: root_authority -> AuthorityNode (nodes[0])
   Property: acting_authority -> AuthorityNode (nodes[-1], who actually decides)
   Property: depth -> int (len(nodes))

   Method: validate_delegation_path() -> bool
     Checks that each node in the chain can legally delegate to the next.
     Rule: a node with delegation_expires_at in the past is invalid.
     Rule: chain must have at least 1 node.
     Raises AuthorityChainValidationError with details if invalid.

   Method: is_human_in_chain() -> bool
     Returns True if any node has node_type == human_role.

   Method: highest_override_authority() -> Optional[AuthorityNode]
     Returns first node where can_override=True.

5. PYDANTIC MODEL: AuthorityChainCreate
   Same as AuthorityChain minus: chain_id, chain_hash, created_at.

6. PYDANTIC MODEL: AuthorityViolation
   violation_id: str
   chain_id: str
   decision_id: str
   violation_type: Literal[
       "exceeded_value_limit",
       "expired_delegation",
       "missing_human_oversight",
       "unauthorized_decision_type",
       "override_without_authority",
   ]
   detected_at: datetime
   details: str

═══ dai/authority/chain.py ═══

CLASS: AuthorityChainBuilder
Fluent builder for constructing authority chains before committing them.

Methods:
begin(decision_type: str, workspace_id: str) -> "AuthorityChainBuilder"
add_node(node: AuthorityNode) -> "AuthorityChainBuilder"
  Appends node to chain. Nodes must be added highest-to-lowest authority.
with_expiry(expires_at: datetime) -> "AuthorityChainBuilder"
build() -> AuthorityChain
  Validates chain, computes chain_hash, returns AuthorityChain.

FUNCTION: validate_decision_against_chain(
    decision: DecisionRecord,
    chain: AuthorityChain,
    policy: PolicyVersion,
) -> list[AuthorityViolation]

Checks:
1. If decision.confidence < policy.max_auto_approve_confidence AND
   decision.human_oversight_required=False → VIOLATION: missing_human_oversight
2. If chain has acting_authority with max_decision_value AND
   decision.metadata.get("decision_value_eur") exceeds it → VIOLATION: exceeded_value_limit
3. If any node in chain has delegation_expires_at in the past at
   decision.decision_timestamp → VIOLATION: expired_delegation
4. If decision.decision_type not in policy.authorized_decision_types → VIOLATION: unauthorized_decision_type
5. If decision.override_applied=True AND chain.highest_override_authority() is None → VIOLATION: override_without_authority

Returns list of violations (empty = valid).

FUNCTION: resolve_chain_at(
    chain_id: str,
    at_timestamp: datetime,
) -> AuthorityChain
Fetches the chain that was effective at a given timestamp.
Used in decision replay to reconstruct exact authority context.

═══ SDK INTEGRATION: Update DecisionRecord and builder ═══

Add to DecisionRecord schema:
  authority_chain_id: Optional[str]
    If set: the chain_id of the AuthorityChain that governed this decision.
    The chain is stored separately. The decision references it by ID.
    This enables chain updates without invalidating decision records.

Add to Decision builder:
  .with_authority_chain(chain_id: str) -> "Decision"
    Sets authority_chain_id on the decision.
    Also fetches chain from server and validates decision against it
    before commit. If violations found:
      - On ErrorPolicy.raise_exception: raises AuthorityViolationError
      - On ErrorPolicy.log_and_continue: records violations in metadata
        as "authority_violations": comma-separated violation types

═══ dai_server/routes/authority.py ═══

Router prefix: /authority-chains

POST /authority-chains
  Body: AuthorityChainCreate
  Response: AuthorityChain (201)

GET /authority-chains/{chain_id}
  Response: AuthorityChain

GET /authority-chains?decision_type={type}&at={timestamp}
  Response: list[AuthorityChain] (chains valid at that time for that type)

POST /authority-chains/{chain_id}/validate
  Body: DecisionRecord
  Response: list[AuthorityViolation]

GET /decisions/{decision_id}/authority-violations
  Response: list[AuthorityViolation]
  Runs validate_decision_against_chain for a stored decision.

═══ Write tests ═══
tests/unit/test_authority_chain.py:
- Build valid chain: 3 nodes, validate passes
- Expired delegation: violation detected
- Missing human oversight: violation detected at low confidence
- Override without authority: violation detected
- is_human_in_chain: True when human node present
- chain_hash: same inputs produce same hash
```

---

## ══════════════════════════════════════════════════════════════
## PROMPT P1-03 — Decision Lineage Graph
## ══════════════════════════════════════════════════════════════

**Session goal:** Model causal relationships between decisions. D2 happened because of D1. This enables root cause analysis and causal audit trails — critical for Article 9 risk management.

```
[PASTE GLOBAL CONTEXT ABOVE FIRST]

TASK: Build dai/lineage/models.py, dai/lineage/graph.py,
      dai_server/routes/lineage.py.

═══ dai/lineage/models.py ═══

1. ENUM: LineageEdgeType
   caused_by | escalated_from | overrides | triggered_by | depends_on | retried_from

2. PYDANTIC MODEL: LineageEdge
   from_decision_id: str (cause)
   to_decision_id: str (effect)
   edge_type: LineageEdgeType
   relationship_note: Optional[str] (max 200 chars, structured code not free text)
   created_at: datetime

3. PYDANTIC MODEL: LineageNode
   decision_id: str
   decision_type: str
   agent_id: str
   outcome: str
   confidence: float
   decision_timestamp: datetime
   exception_applied: bool
   override_applied: bool
   depth: int (distance from root decision in the lineage tree)

4. PYDANTIC MODEL: DecisionLineageGraph
   root_decision_id: str
   nodes: list[LineageNode]
   edges: list[LineageEdge]
   max_depth: int
   total_nodes: int
   contains_exception: bool (True if any node has exception_applied=True)
   contains_override: bool
   built_at: datetime

5. PYDANTIC MODEL: LineageRootCause
   root_decision_id: str
   root_agent_id: str
   root_outcome: str
   root_exception_type: Optional[str]
   path_to_failure: list[str] (decision_ids in causal order)
   contributing_factors: list[str] (structured codes)
   analysis_timestamp: datetime

═══ dai/lineage/graph.py ═══

Uses networkx.DiGraph internally.

CLASS: DecisionLineageBuilder
Builds lineage graphs from stored decision records.

Methods:

add_edge(
    from_decision_id: str,
    to_decision_id: str,
    edge_type: LineageEdgeType,
    relationship_note: Optional[str] = None,
) -> None
  Stores a LineageEdge. Both decision_ids must exist in the ledger.
  Creates a directed edge: from → to.
  (from = cause, to = effect)

build_graph(root_decision_id: str, max_depth: int = 10) -> DecisionLineageGraph
  Starting from root_decision_id, traverse all edges up to max_depth.
  Build networkx.DiGraph from edges.
  Fetch LineageNode details for each node from the decision store.
  Return DecisionLineageGraph.

find_root_cause(decision_id: str) -> LineageRootCause
  Walk backwards from decision_id through caused_by edges.
  Find the earliest decision in the chain (root).
  Analyse root: what exception/override/policy triggered the cascade?
  Return LineageRootCause with path and contributing_factors.

  Contributing factors are STRUCTURED CODES (not free text):
  ["root_exception:conservative_fallback",
   "policy_version:3.1.0",
   "confidence_below_threshold:0.67",
   "override_applied:true"]

get_descendants(decision_id: str) -> list[str]
  All decision_ids downstream of this decision.

get_ancestors(decision_id: str) -> list[str]
  All decision_ids upstream (causes) of this decision.

visualise_graph(graph: DecisionLineageGraph) -> dict
  Returns a JSON-serialisable dict compatible with D3.js force graph:
  {"nodes": [...], "links": [...]}
  Node fields: id, label, type, outcome, depth, is_exception, is_override
  Link fields: source, target, type

═══ SDK INTEGRATION: Add to Decision builder ═══

Add to DecisionRecord schema:
  parent_decision_id: Optional[str]
    The decision that directly caused this decision to be made.
  parent_edge_type: Optional[LineageEdgeType]
    How this decision relates to parent (escalated_from, triggered_by, etc.)

Add to Decision builder:
  .caused_by(
      parent_decision_id: str,
      edge_type: LineageEdgeType = LineageEdgeType.caused_by,
  ) -> "Decision"
  Sets parent_decision_id and parent_edge_type.
  On commit: also creates a LineageEdge record via the server.

═══ dai_server/routes/lineage.py ═══

Router prefix: /lineage

POST /lineage/edges
  Body: LineageEdge
  Response: LineageEdge (201)
  Stores a causal relationship between two decisions.

GET /decisions/{decision_id}/lineage
  Query params: max_depth (int, default 10), direction (upstream|downstream|both)
  Response: DecisionLineageGraph

GET /decisions/{decision_id}/root-cause
  Response: LineageRootCause

GET /decisions/{decision_id}/ancestors
  Response: list[LineageNode] (all upstream decisions)

GET /decisions/{decision_id}/descendants
  Response: list[LineageNode] (all downstream decisions)

GET /lineage/visualise/{decision_id}
  Response: D3.js-compatible graph JSON

═══ SQLAlchemy model: DecisionLineageEdgeORM ═══

Table: decision_lineage_edges
  from_decision_id: String(36), not null, indexed
  to_decision_id: String(36), not null, indexed
  edge_type: String(100), not null
  relationship_note: String(200), nullable
  created_at: DateTime(timezone=True), not null
  workspace_id: String(36), not null, indexed

Primary key: (from_decision_id, to_decision_id)

═══ Write tests ═══
tests/unit/test_lineage_graph.py:
- Add 5 edges, build graph: correct node count
- find_root_cause: traverses to earliest node
- get_ancestors / get_descendants: correct sets
- visualise_graph: valid D3.js format output
- max_depth: graph stops at specified depth
```

---

## ══════════════════════════════════════════════════════════════
## PROMPT P1-04 — Decision Replay Engine
## ══════════════════════════════════════════════════════════════

**Session goal:** Build the most defensible feature in the entire product. Decision replay allows you to re-run a historical decision under different conditions and see exactly what changes. This is the feature that closes enterprise deals.

```
[PASTE GLOBAL CONTEXT ABOVE FIRST]

TASK: Build dai/replay/models.py, dai/replay/engine.py,
      dai_server/routes/replay.py.

═══ dai/replay/models.py ═══

1. ENUM: ReplayVariableType
   model_version | policy_version | confidence_threshold |
   context_completeness | evidence_set | authority_chain

2. PYDANTIC MODEL: ReplayVariable
   variable_type: ReplayVariableType
   original_value: str (JSON-serialised original)
   substituted_value: str (JSON-serialised replacement)
   description: str (why this variable was changed)

3. PYDANTIC MODEL: ReplayRequest
   original_decision_id: str (the decision to replay)
   variables: list[ReplayVariable] (what to change)
   replay_reason: str (structured code, not free text):
     Literal["audit_investigation", "policy_update_impact",
             "model_update_validation", "incident_analysis",
             "compliance_check", "regression_test"]
   requested_by: str (role/system requesting replay)
   workspace_id: str

4. PYDANTIC MODEL: OutcomeDiff
   field: str (which field differed)
   original: str
   replayed: str
   significance: Literal["critical", "significant", "minor"]

   CRITICAL: outcome or confidence changed by >0.2
   SIGNIFICANT: confidence changed by 0.05-0.2, exception_applied changed
   MINOR: metadata or non-outcome fields changed

5. PYDANTIC MODEL: ReplayResult
   replay_id: str (UUIDv7)
   original_decision_id: str
   replayed_decision_id: Optional[str]
     (if the replay result is itself committed as a new decision record)
   variables_applied: list[ReplayVariable]
   original_outcome: str
   replayed_outcome: str
   outcome_changed: bool
   outcome_diffs: list[OutcomeDiff]
   original_confidence: float
   replayed_confidence: float
   confidence_delta: float
   exceptions_introduced: list[str]
   exceptions_removed: list[str]
   authority_violations_introduced: list[str]
   policy_diff_applied: Optional[PolicyDiff]
   replay_timestamp: datetime
   replay_reason: str
   requested_by: str
   summary: str (auto-generated structured summary)

═══ dai/replay/engine.py ═══

CLASS: DecisionReplayEngine

Constructor:
  decision_store: DAI client reference
  policy_store: PolicyStore reference
  authority_store: AuthorityChainStore reference

METHOD: async replay(request: ReplayRequest) -> ReplayResult

Algorithm:
1. Fetch original DecisionRecord from decision store
2. Resolve original policy via policy_store.resolve_at(
     policy_id=original.policy_id,
     at_timestamp=original.decision_timestamp
   )
3. Fetch original AuthorityChain if authority_chain_id is set
4. Build a "simulated" DecisionRecord by applying variables:

   For ReplayVariable(variable_type=policy_version, substituted_value="3.3.0"):
     - Fetch PolicyVersion 3.3.0
     - Check if it changes: max_auto_approve_confidence, clauses, exception_types
     - Apply these changes to simulated record

   For ReplayVariable(variable_type=confidence_threshold, ...):
     - Apply new threshold to simulated record
     - Re-evaluate human_oversight_required against new threshold

   For ReplayVariable(variable_type=model_version, ...):
     - Record that model version changed (cannot re-execute LLM)
     - Flag: outcome_changed = UNKNOWN (cannot determine without re-execution)
     - Note in summary: "Model version change requires re-execution to confirm outcome"

5. Compute outcome_diffs between original and simulated record
6. Run validate_decision_against_chain on simulated record
7. Build ReplayResult
8. Commit replay record to ledger as a new decision with:
   decision_type = f"replay:{original.decision_type}"
   metadata: {"replayed_from": original.decision_id, "replay_id": replay_id}

CRITICAL DESIGN NOTE:
The replay engine does NOT re-invoke the AI model. It simulates what
WOULD HAVE HAPPENED under different policy/authority conditions.
For model version changes, it flags the result as REQUIRES_REEXECUTION.
This is the correct approach: we are auditing policy and authority
changes, not re-running AI inference.

METHOD: async batch_replay(
    decision_ids: list[str],
    variable: ReplayVariable,
) -> list[ReplayResult]
Applies the same variable change to multiple decisions.
Use case: "What would happen to all claims decisions from Q1 2026
if we had used policy version 3.3.0 instead of 3.2.1?"

METHOD: async policy_impact_analysis(
    policy_id: str,
    from_version: str,
    to_version: str,
    decision_types: list[str],
    from_timestamp: datetime,
    to_timestamp: datetime,
) -> PolicyImpactReport
Fetches all decisions in time range using old policy version.
Batch replays them with new policy version.
Returns PolicyImpactReport with:
  - Count of decisions where outcome would change
  - Count where exception_applied would change
  - Count where human oversight threshold triggered differently
  - Sample of highest-significance differences

═══ PYDANTIC MODEL: PolicyImpactReport ═══

policy_id: str
from_version: str
to_version: str
analysis_period_from: datetime
analysis_period_to: datetime
total_decisions_analysed: int
outcome_changes: int
outcome_change_rate: float
exception_changes: int
oversight_threshold_changes: int
highest_significance_cases: list[ReplayResult] (top 10)
risk_assessment: Literal["safe_to_deploy", "review_required", "high_risk"]
risk_assessment_rationale: str
generated_at: datetime

═══ dai_server/routes/replay.py ═══

Router prefix: /replay

POST /decisions/{decision_id}/replay
  Body: ReplayRequest
  Response: ReplayResult (201)

POST /replay/batch
  Body: {decision_ids: list[str], variable: ReplayVariable}
  Response: list[ReplayResult]

POST /replay/policy-impact
  Body: PolicyImpactAnalysisRequest
  Response: PolicyImpactReport
  (Long-running: return 202 Accepted with job_id, poll GET /replay/jobs/{job_id})

GET /replay/jobs/{job_id}
  Response: {"status": "pending|running|complete|failed", "result": Optional[PolicyImpactReport]}

GET /decisions/{decision_id}/replays
  Response: list[ReplayResult] (all replays of this decision, newest first)

═══ Write tests ═══
tests/unit/test_replay_engine.py:
- Replay with policy_version change: outcome_diffs computed correctly
- Replay with confidence_threshold change: oversight flag changes detected
- Replay with model_version change: flagged as REQUIRES_REEXECUTION
- No variable change: outcome_changed=False, zero diffs
- policy_impact_analysis: correct change rate computed on 10 decisions
```

---

## ══════════════════════════════════════════════════════════════
## PROMPT P1-05 — Policy Drift Detector
## ══════════════════════════════════════════════════════════════

**Session goal:** Build the intelligence layer that detects when agent behaviour diverges from policy intent over time. This is the Article 9 continuous risk management system and the feature that makes the product "sticky."

```
[PASTE GLOBAL CONTEXT ABOVE FIRST]

TASK: Build dai/intelligence/drift.py, dai/intelligence/overrides.py,
      dai/intelligence/consistency.py, dai_server/routes/intelligence.py.

═══ dai/intelligence/drift.py ═══

WHAT POLICY DRIFT IS:
A policy defines that claims with confidence >= 0.85 should be auto-approved.
Over time, the agent starts approving claims at confidence 0.78. The policy
hasn't changed. The agent's behaviour has drifted. This is a risk management
failure that must be detected and reported.

PYDANTIC MODEL: DriftSignal
  signal_id: str
  workspace_id: str
  agent_id: str
  decision_type: str
  policy_id: str
  policy_version: str
  drift_type: Literal[
    "confidence_threshold_drift",      # avg confidence drifting below policy min
    "exception_rate_spike",            # exception rate above baseline
    "override_rate_spike",             # human overrides increasing
    "outcome_distribution_shift",      # outcome mix changing unexpectedly
    "policy_clause_bypass",            # decisions made without applying required clauses
    "authority_scope_creep",           # decisions exceeding authorized scope
  ]
  severity: Literal["low", "medium", "high", "critical"]
  baseline_period_from: datetime
  baseline_period_to: datetime
  observation_period_from: datetime
  observation_period_to: datetime
  baseline_value: float
  observed_value: float
  delta: float
  delta_percentage: float
  threshold_for_alert: float
  sample_decision_ids: list[str] (up to 5 decisions showing the drift)
  detected_at: datetime
  details: str (structured, max 500 chars)

SEVERITY THRESHOLDS (defaults, configurable per workspace):
  confidence_threshold_drift:
    LOW: observed_avg < policy_threshold * 0.98
    MEDIUM: observed_avg < policy_threshold * 0.95
    HIGH: observed_avg < policy_threshold * 0.90
    CRITICAL: observed_avg < policy_threshold * 0.85
  exception_rate_spike:
    LOW: +25% vs baseline
    MEDIUM: +50%
    HIGH: +100%
    CRITICAL: +200%
  override_rate_spike:
    LOW: +30% vs baseline
    MEDIUM: +60%
    HIGH: +120%
    CRITICAL: +250%

CLASS: PolicyDriftDetector

Constructor:
  db_session: AsyncSession
  workspace_id: str

METHOD: async detect_drift(
    agent_id: str,
    decision_type: str,
    policy_id: str,
    observation_window_days: int = 7,
    baseline_window_days: int = 30,
) -> list[DriftSignal]

Algorithm:
1. Fetch PolicyVersion for policy_id (current active version)
2. Query decisions for OBSERVATION period (last observation_window_days)
3. Query decisions for BASELINE period (previous baseline_window_days)
4. Compute metrics for both periods using pandas:
   - avg_confidence, std_confidence
   - exception_rate = exceptions / total
   - override_rate = overrides / total
   - outcome_distribution = {outcome: count/total}
   - clauses_applied_coverage = how often required clauses appear
5. For each drift_type: compare observation vs baseline
6. Apply severity thresholds
7. For signals above LOW: fetch sample decision_ids
8. Return list of DriftSignal

METHOD: async scan_workspace(
    observation_window_days: int = 7,
) -> list[DriftSignal]
Runs detect_drift for every unique (agent_id, decision_type, policy_id)
combination in the workspace.
Scheduled to run daily (see PROMPT P1-07).

═══ dai/intelligence/overrides.py ═══

WHAT OVERRIDE CLUSTERING IS:
When humans override automated decisions, the patterns reveal where the
policy or model is failing. If 80% of overrides for claims_triage happen
when confidence is between 0.70-0.80 on a specific policy clause,
that clause may be miscalibrated.

PYDANTIC MODEL: OverrideCluster
  cluster_id: str
  workspace_id: str
  agent_id: str
  decision_type: str
  cluster_size: int
  pattern_type: Literal[
    "confidence_band",      # overrides cluster in a confidence range
    "policy_clause",        # overrides cluster around specific clause
    "time_of_day",          # overrides cluster at specific times
    "subject_type",         # overrides cluster on specific subject patterns
    "exception_type",       # overrides happen after specific exceptions
  ]
  pattern_description: str (structured, max 300 chars)
  confidence_range_min: Optional[float]
  confidence_range_max: Optional[float]
  most_common_override_justification: Optional[str]
  sample_decision_ids: list[str] (up to 10)
  period_from: datetime
  period_to: datetime
  detected_at: datetime
  recommendation: Literal[
    "review_policy_clause",
    "adjust_confidence_threshold",
    "retrain_model",
    "add_exception_type",
    "escalate_to_risk_review",
  ]

CLASS: OverrideClusterAnalyser

METHOD: async analyse(
    agent_id: str,
    decision_type: str,
    period_from: datetime,
    period_to: datetime,
    min_cluster_size: int = 5,
) -> list[OverrideCluster]

Fetch all override decisions in period.
Use pandas groupby to cluster by:
  - confidence bands (0.1 width buckets)
  - policy clauses applied
  - override justification
  - hour of day (time_of_day pattern)
Return clusters where cluster_size >= min_cluster_size.
Assign recommendation based on dominant pattern.

═══ dai/intelligence/consistency.py ═══

WHAT CROSS-AGENT CONSISTENCY IS:
Two agents governed by the same policy should produce similar outcomes for
similar inputs. If agent-A approves 90% of claims and agent-B approves 60%
for the same claim types, there is an inconsistency that must be investigated.

PYDANTIC MODEL: ConsistencyReport
  workspace_id: str
  decision_type: str
  policy_id: str
  policy_version: str
  period_from: datetime
  period_to: datetime
  agents_analysed: list[str]
  outcome_distributions: dict[str, dict[str, float]]
    # {agent_id: {outcome: percentage}}
  max_approval_rate_delta: float
    # largest difference in approval rate between any two agents
  max_exception_rate_delta: float
  max_confidence_delta: float
  consistency_score: float (0.0 = completely inconsistent, 1.0 = identical)
  inconsistent_pairs: list[tuple[str, str]]
    # agent pairs with delta > threshold
  severity: Literal["consistent", "minor_variation", "significant_variation", "critical_inconsistency"]
  sample_divergent_decisions: list[str]
  generated_at: datetime

CLASS: CrossAgentConsistencyChecker

METHOD: async check(
    decision_type: str,
    policy_id: str,
    period_from: datetime,
    period_to: datetime,
) -> ConsistencyReport

Fetch all decisions of this type for this policy in period.
Group by agent_id.
Compute outcome distributions, avg confidence, exception rates per agent.
Compute pairwise deltas.
Compute consistency_score = 1 - (max_delta / possible_range).
Return ConsistencyReport.

═══ dai_server/routes/intelligence.py ═══

Router prefix: /intelligence

GET /intelligence/drift
  Query: agent_id, decision_type, policy_id,
         observation_window_days (default 7),
         baseline_window_days (default 30)
  Response: list[DriftSignal]

GET /intelligence/drift/workspace-scan
  Response: list[DriftSignal] (full workspace scan)

GET /intelligence/overrides/clusters
  Query: agent_id, decision_type, from, to, min_cluster_size
  Response: list[OverrideCluster]

GET /intelligence/consistency
  Query: decision_type, policy_id, from, to
  Response: ConsistencyReport

GET /intelligence/summary
  Response: IntelligenceSummary
  {
    "active_drift_signals": int,
    "critical_signals": int,
    "override_clusters": int,
    "consistency_issues": int,
    "agents_monitored": int,
    "last_scan_at": datetime,
  }
  This is the "status at a glance" endpoint for a future dashboard.

═══ Write tests ═══
tests/unit/test_drift_detector.py:
- Confidence below threshold: drift signal generated at correct severity
- Exception rate spike: detected above LOW threshold
- No drift: empty signal list returned
- Scan workspace: called for each unique agent/type/policy combination

tests/unit/test_override_cluster.py:
- Confidence band cluster: detected when 5+ overrides in same band
- Small cluster below min_size: not returned
- Recommendation assignment: correct code for pattern type

tests/unit/test_consistency.py:
- Two agents same outcomes: consistency_score near 1.0
- Two agents divergent: severity=significant_variation
- Single agent: no inconsistency computed (requires 2+)
```

---

## ══════════════════════════════════════════════════════════════
## PROMPT P1-06 — Multi-Tenant Workspace & RBAC
## ══════════════════════════════════════════════════════════════

**Session goal:** Add workspace isolation and role-based access control. Without this, no enterprise will deploy a shared instance.

```
[PASTE GLOBAL CONTEXT ABOVE FIRST]

TASK: Build workspace isolation and RBAC across the entire server.
      This is a cross-cutting concern — it modifies existing routes
      as well as adding new ones.

═══ dai/authority/models.py (additions) ═══

ENUM: WorkspaceRole
  owner | admin | developer | auditor | read_only

  Permissions by role:
  owner:     all operations including workspace deletion
  admin:     all operations except workspace deletion
  developer: ingest decisions, read own decisions, no intelligence routes
  auditor:   read all decisions, run exports, view intelligence — no ingest
  read_only: read decisions only, no exports, no intelligence

PYDANTIC MODEL: Workspace
  workspace_id: str (UUIDv7)
  name: str
  description: str
  created_at: datetime
  owner_email: str (for contact, not stored in decision records)
  retention_policy_days: int (default 180, minimum required by EU AI Act)
  max_decisions_per_day: int (rate limit, 0 = unlimited)
  allowed_decision_types: list[str] (empty = all allowed)
  is_active: bool

PYDANTIC MODEL: WorkspaceAPIKey
  key_id: str (UUIDv7)
  workspace_id: str
  role: WorkspaceRole
  name: str (descriptive, e.g. "production-claims-agent")
  key_hash: str (SHA-256 of actual key — key itself never stored)
  key_prefix: str (first 8 chars of key, for identification)
  created_at: datetime
  expires_at: Optional[datetime]
  last_used_at: Optional[datetime]
  is_active: bool

PYDANTIC MODEL: WorkspaceCreate
  name: str
  description: str
  owner_email: str
  retention_policy_days: int = 180
  max_decisions_per_day: int = 0
  allowed_decision_types: list[str] = []

═══ dai_server/auth.py (new file) ═══

Middleware and dependency for API key authentication + RBAC.

FUNCTION: hash_api_key(key: str) -> str
  SHA-256(key).hexdigest()

FUNCTION: generate_api_key() -> tuple[str, str]
  Returns (plain_key, key_hash).
  plain_key = f"dlk_{secrets.token_urlsafe(32)}"
    (dl = DecisionLedger, k = key, then random)
  key_hash = hash_api_key(plain_key)
  Return (plain_key, key_hash) — plain_key shown ONCE on creation.

FASTAPI DEPENDENCY: get_current_workspace(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> tuple[Workspace, WorkspaceAPIKey]
  1. Extract key from X-API-Key header (also accept Authorization: Bearer)
  2. Compute key_hash = SHA-256(key)
  3. Lookup WorkspaceAPIKeyORM by key_hash
  4. If not found: HTTPException(401)
  5. If expired: HTTPException(401, "API key expired")
  6. If workspace not active: HTTPException(403)
  7. Update last_used_at asynchronously (fire-and-forget)
  8. Return (workspace, api_key)

FASTAPI DEPENDENCY: require_role(*roles: WorkspaceRole)
  Returns a dependency that checks current key's role is in allowed roles.
  Usage: Depends(require_role(WorkspaceRole.admin, WorkspaceRole.owner))
  Raises HTTPException(403, "Insufficient permissions") if not allowed.

═══ MODIFY ALL EXISTING ROUTES ═══

Add workspace scoping to every existing route:

1. All ingest routes: add workspace_id = workspace.workspace_id to
   every stored record. Require developer role minimum.

2. All query routes: add WHERE workspace_id = workspace.workspace_id
   to every query. Require read_only role minimum.

3. All verify routes: scope to workspace_id. Require auditor role minimum.

4. All export routes: scope to workspace_id. Require auditor role minimum.

5. All policy routes: scope to workspace_id. Require admin for write,
   auditor for read.

6. All intelligence routes: scope to workspace_id. Require auditor role.

7. All replay routes: scope to workspace_id. Require admin role.

═══ dai_server/routes/workspaces.py ═══

Special: workspace creation route does NOT require existing API key.
It uses a master admin key set via MASTER_API_KEY environment variable.

POST /workspaces
  Header: X-Master-Key (validates against MASTER_API_KEY env var)
  Body: WorkspaceCreate
  Response: {"workspace": Workspace, "owner_api_key": str}
    Returns the plain owner API key ONCE. Never again.

GET /workspaces/me
  Requires: any valid API key
  Response: Workspace (the workspace for the current key)

POST /workspaces/me/api-keys
  Requires: admin or owner role
  Body: {"name": str, "role": WorkspaceRole, "expires_in_days": Optional[int]}
  Response: {"api_key": WorkspaceAPIKey, "plain_key": str}
    Returns plain key ONCE.

GET /workspaces/me/api-keys
  Requires: admin or owner role
  Response: list[WorkspaceAPIKey] (key_hash never returned, key_prefix only)

DELETE /workspaces/me/api-keys/{key_id}
  Requires: admin or owner role
  Sets is_active=False.

═══ SQLAlchemy models ═══

WorkspaceORM — Table: workspaces
WorkspaceAPIKeyORM — Table: workspace_api_keys (key_hash indexed for fast lookup)

New Alembic migration: 0002_add_workspaces.py
  - Create workspaces table
  - Create workspace_api_keys table
  - Add workspace_id column to decisions, policy_versions,
    authority_chains, decision_lineage_edges tables
  - Add workspace_id to all relevant indexes

═══ Write tests ═══
tests/unit/test_auth.py:
- generate_api_key: produces dlk_ prefix, 44-char suffix
- hash_api_key: deterministic SHA-256
- get_current_workspace: valid key succeeds
- get_current_workspace: invalid key raises 401
- get_current_workspace: expired key raises 401
- require_role: correct role passes
- require_role: wrong role raises 403
- Cross-workspace isolation: workspace A cannot see workspace B decisions
```

---

## ══════════════════════════════════════════════════════════════
## PROMPT P1-07 — Post-Market Monitoring (Article 12)
## ══════════════════════════════════════════════════════════════

**Session goal:** Build the Article 12 continuous monitoring system and scheduled jobs. This is what transforms DecisionLedger from "compliance logging" to "continuous risk management infrastructure."

```
[PASTE GLOBAL CONTEXT ABOVE FIRST]

TASK: Build dai_server/monitoring/article12.py,
      dai_server/monitoring/scheduler.py,
      and a new export endpoint for Article 12 reports.

EU AI Act Article 12 requires: automatic logging of system events to
facilitate risk identification and post-market monitoring. This is
DISTINCT from Article 19 (which covers individual decision logs).
Article 12 is about system-level patterns, anomalies, and risk signals.

═══ dai_server/monitoring/article12.py ═══

PYDANTIC MODEL: MonitoringEvent
  event_id: str (UUIDv7)
  workspace_id: str
  event_type: Literal[
    "drift_signal_detected",
    "override_cluster_detected",
    "consistency_violation",
    "chain_integrity_failure",
    "authority_violation",
    "high_exception_rate",
    "policy_version_change",
    "agent_behaviour_change",
    "corrective_action_recommended",
  ]
  severity: Literal["info", "warning", "high", "critical"]
  agent_id: Optional[str]
  decision_type: Optional[str]
  policy_id: Optional[str]
  event_timestamp: datetime
  details: str (max 500 chars)
  related_decision_ids: list[str]
  requires_corrective_action: bool
  corrective_action_taken: Optional[str]
  corrective_action_at: Optional[datetime]

PYDANTIC MODEL: Article12Report
  workspace_id: str
  reporting_period_from: datetime
  reporting_period_to: datetime
  generated_at: datetime

  system_health:
    total_decisions: int
    total_agents_active: int
    total_decision_types: int
    chain_integrity_status: Literal["verified", "broken", "not_verified"]
    chain_broken_at: Optional[str]

  risk_signals:
    drift_signals_detected: int
    drift_signals_critical: int
    override_clusters_detected: int
    consistency_violations: int
    authority_violations: int

  corrective_actions:
    required: int
    completed: int
    pending: int
    overdue: int

  policy_changes:
    policy_versions_changed: int
    policies_deprecated: int
    impact_analyses_run: int

  anomaly_timeline: list[MonitoringEvent]
    (all events in period, ordered by timestamp)

  risk_assessment: Literal[
    "system_operating_normally",
    "minor_anomalies_detected",
    "significant_risks_require_review",
    "critical_risks_require_immediate_action",
  ]

  next_review_recommended_by: datetime
  regulatory_notes: str
    ("This report covers Article 12 EU AI Act post-market monitoring
     requirements for the period {from} to {to}.")

FUNCTION: generate_article12_report(
    workspace_id: str,
    from_timestamp: datetime,
    to_timestamp: datetime,
    db: AsyncSession,
) -> Article12Report

Aggregates:
1. Decision counts from ledger
2. Chain integrity via verify_chain
3. Drift signals from intelligence layer
4. Override clusters from intelligence layer
5. Authority violations from authority layer
6. MonitoringEvents from monitoring_events table
7. Policy changes from policy_versions table
Builds and returns Article12Report.

═══ dai_server/monitoring/scheduler.py ═══

Uses APScheduler (add to dependencies: apscheduler>=3.10.0).

Jobs to schedule:

1. DAILY at 02:00 UTC: workspace_drift_scan()
   For each active workspace:
     Run PolicyDriftDetector.scan_workspace()
     For each DriftSignal with severity >= "medium":
       Create MonitoringEvent(event_type="drift_signal_detected")
       If severity == "critical": set requires_corrective_action=True

2. DAILY at 03:00 UTC: chain_integrity_check()
   For each active workspace:
     Run verify_chain for last 24 hours of decisions
     If chain broken: create MonitoringEvent(
       event_type="chain_integrity_failure", severity="critical"
     )

3. WEEKLY on Monday 04:00 UTC: consistency_check()
   For each workspace: run CrossAgentConsistencyChecker
   If severity >= "significant_variation": create MonitoringEvent

4. ON POLICY_VERSION_CHANGE: policy_change_event()
   Triggered when new PolicyVersion is created.
   Create MonitoringEvent(event_type="policy_version_change")
   Queue PolicyImpactAnalysis for affected decisions.

Scheduler startup: integrate with FastAPI lifespan events.
Scheduler runs in background thread, does not block request handling.

═══ SQLAlchemy model: MonitoringEventORM ═══

Table: monitoring_events (append-only like decisions)
All fields from MonitoringEvent.
Indexed: workspace_id, event_type, severity, event_timestamp.

New Alembic migration: 0003_add_monitoring_events.py

═══ Add routes to dai_server/routes/ ═══

POST /export/article12
  Body: {from_timestamp, to_timestamp}
  Response: Article12Report as JSON (or ?format=pdf for PDF)
  Requires: auditor role

GET /monitoring/events
  Query: from, to, severity, event_type, agent_id
  Response: list[MonitoringEvent]
  Requires: auditor role

POST /monitoring/events/{event_id}/corrective-action
  Body: {action_taken: str, action_timestamp: datetime}
  Updates corrective_action_taken and corrective_action_at.
  Creates audit trail of the corrective action itself.
  Requires: admin role

═══ Write tests ═══
tests/unit/test_article12.py:
- generate_article12_report: correct counts for 50 mixed decisions
- risk_assessment: "critical" when drift_signals_critical > 0
- corrective_actions: overdue count when action_at > 7 days past required
tests/integration/test_scheduler.py:
- drift_scan: creates MonitoringEvent for critical DriftSignal
- chain_check: creates critical event when chain broken
```

---

## ══════════════════════════════════════════════════════════════
## PROMPT P1-08 — Data Retention & Integrity Controls
## ══════════════════════════════════════════════════════════════

**Session goal:** Build legal-grade data retention, with EU AI Act Article 18 compliant retention periods, tamper-evident audit packages, and controlled data lifecycle.

```
[PASTE GLOBAL CONTEXT ABOVE FIRST]

TASK: Build retention controls, audit package generation, and data
      lifecycle management.

EU AI Act Article 18: Documentation keeping.
Technical documentation must be retained for 10 years for high-risk AI.
Decision logs must be retained for minimum 6 months.

═══ PYDANTIC MODEL: RetentionPolicy ═══

workspace_id: str
decision_record_retention_days: int (minimum 180, EU AI Act Article 19)
policy_document_retention_days: int (minimum 3650, Article 18: 10 years)
monitoring_event_retention_days: int (minimum 365)
audit_package_retention_days: int (minimum 3650)
auto_archive_after_days: int (move old records to cold storage after N days)
legal_hold_active: bool (if True, no records deleted regardless of age)
legal_hold_reason: Optional[str]
legal_hold_activated_at: Optional[datetime]

Validator: decision_record_retention_days >= 180
Validator: policy_document_retention_days >= 3650

═══ FUNCTION: generate_audit_package ═══

PYDANTIC MODEL: AuditPackage
  package_id: str (UUIDv7)
  workspace_id: str
  period_from: datetime
  period_to: datetime
  generated_at: datetime
  requested_by: str
  purpose: Literal["regulatory_audit", "internal_review",
                   "incident_investigation", "legal_proceedings",
                   "conformity_assessment"]

  contents:
    decision_count: int
    chain_integrity: ChainVerifyResult
    article19_report: Article19Export
    article12_report: Article12Report
    policy_versions_snapshot: list[PolicyVersion]
    authority_chains_snapshot: list[AuthorityChain]
    drift_signals: list[DriftSignal]
    authority_violations: list[AuthorityViolation]

  integrity:
    package_hash: str (SHA-256 of entire package contents)
    signed_at: datetime
    signature_method: "sha256_self_signed"

FUNCTION: generate_audit_package(
    workspace_id: str,
    period_from: datetime,
    period_to: datetime,
    purpose: str,
    requested_by: str,
    db: AsyncSession,
) -> AuditPackage

Assembles all reports, computes package_hash, returns AuditPackage.
Stores AuditPackage metadata in DB (not contents — too large).
Contents returned to caller for download.

POST /export/audit-package
  Body: AuditPackageRequest
  Response: AuditPackage as JSON
  Also supports ?format=zip to return a ZIP archive containing:
    - article19_report.json
    - article19_report.pdf
    - article12_report.json
    - decisions.jsonl (newline-delimited JSON of all decision records)
    - policy_versions.json
    - authority_chains.json
    - chain_integrity.json
    - package_manifest.json (hash + metadata)
  Requires: owner or admin role

═══ RETENTION ENFORCEMENT ═══

SCHEDULED JOB (add to scheduler.py): daily at 01:00 UTC:
apply_retention_policy(workspace_id)

For each workspace:
1. Check legal_hold_active — if True, skip entirely.
2. Find decisions older than decision_record_retention_days
3. Do NOT delete them — mark status="archived" (append-only, never deleted)
4. Move their full_record_json to cold storage reference
   (In Phase 0 this means: compress and store in GCP Cloud Storage,
    replace full_record_json with {"archived": true, "location": "gcs://..."})
5. Record a MonitoringEvent(event_type="records_archived", count=N)

IMPORTANT: DecisionLedger NEVER deletes records.
Append-only means append-only. Archiving moves content to cold storage
but the record stub (with hashes intact) remains in the hot DB forever.
This maintains chain integrity while managing storage costs.

POST /workspaces/me/legal-hold
  Body: {"reason": str}
  Activates legal hold. Requires owner role.
  Creates MonitoringEvent(event_type="legal_hold_activated").

DELETE /workspaces/me/legal-hold
  Deactivates legal hold. Requires owner role.
  Creates MonitoringEvent(event_type="legal_hold_deactivated").
```

---

## ══════════════════════════════════════════════════════════════
## PROMPT P1-09 — CLI Phase 1 Extensions
## ══════════════════════════════════════════════════════════════

**Session goal:** Extend the CLI with all Phase 1 operations so compliance teams and engineers can work without touching the API directly.

```
[PASTE GLOBAL CONTEXT ABOVE FIRST]

TASK: Extend cli/main.py with Phase 1 commands.
      Do not modify existing commands — only add new ones.

NEW COMMANDS:

1. dai policy create
   Interactive wizard to create a new PolicyVersion.
   Prompts: policy_id, version, title, effective_from,
            max_auto_approve_confidence, authorized_decision_types
   Outputs: created PolicyVersion as YAML + stored policy_hash

2. dai policy list [policy_id]
   Lists all versions of a policy in a Rich table:
   version | status | effective_from | effective_to | change_type

3. dai policy diff [policy_id] [from_version] [to_version]
   Shows PolicyDiff in a Rich side-by-side comparison:
   ADDED clauses: green
   REMOVED clauses: red
   MODIFIED clauses: yellow
   Threshold changes: highlighted

4. dai policy resolve [policy_id] --at [timestamp]
   Answers: "Which policy version was active at this moment?"
   Output: PolicyVersion YAML

5. dai intelligence drift [--agent] [--type] [--window 7]
   Lists DriftSignals in a Rich table.
   CRITICAL signals shown in red, HIGH in yellow.
   Exit code 1 if any CRITICAL signals detected (enables CI integration).

6. dai intelligence summary
   One-line health summary:
   ✓ No drift signals · ✓ Chain intact · ✓ 2 agents consistent
   or:
   ⚠ 3 drift signals (1 CRITICAL) · ✓ Chain intact · ✗ Inconsistency detected

7. dai replay [decision_id]
   Interactive replay wizard:
   1. Show original decision details
   2. Prompt: "What do you want to change?" (select variable type)
   3. Prompt for substituted value
   4. Run replay
   5. Show outcome diff in Rich side-by-side
   CRITICAL diff: red highlight
   UNCHANGED: grey

8. dai audit-package
   Options: --from, --to, --purpose, --format (json|zip)
   Generates Article 19 + Article 12 + full audit package.
   Shows progress bar.
   Saves to: dai_audit_{workspace}_{from}_{to}.zip

9. dai workspace create
   Prompts for workspace details.
   Outputs: workspace_id + owner API key (shown ONCE, prompts to save).

10. dai workspace status
    Shows workspace info + key roles + rate limits + retention policy.

For all new commands:
- Rich tables for list outputs
- Rich panels for single item outputs
- Consistent color coding: green=good, yellow=warning, red=error/critical
- --json flag on all commands for machine-readable output (CI integration)
- Exit codes: 0=success, 1=critical findings, 2=error
```

---

## ══════════════════════════════════════════════════════════════
## PROMPT P1-10 — Phase 1 Integration Tests
## ══════════════════════════════════════════════════════════════

**Session goal:** Build the complete Phase 1 integration test suite. These tests prove the system works end-to-end and serve as regression protection.

```
[PASTE GLOBAL CONTEXT ABOVE FIRST]

TASK: Build tests/integration/phase1/ with full integration tests.

tests/integration/phase1/test_policy_lifecycle.py:
- Create policy v1.0.0, create v2.0.0: v1 automatically superseded
- Resolve policy at timestamp before v2 effective date: returns v1
- Resolve policy at timestamp after v2 effective date: returns v2
- Generate PolicyDiff v1→v2: detects clause additions
- Deprecate v2: status updated, still resolvable historically

tests/integration/phase1/test_authority_chain_integration.py:
- Build 3-node chain (Board → CRO → Agent)
- Commit decision referencing chain_id
- Validate: no violations for confidence 0.92 with policy threshold 0.85
- Validate: VIOLATION missing_human_oversight when confidence 0.70 < 0.85
- Validate: VIOLATION override_without_authority when override=True, no override-capable node

tests/integration/phase1/test_decision_lineage_integration.py:
- Commit parent decision → child decision with caused_by edge
- Build lineage graph: 2 nodes, 1 edge, correct depth
- find_root_cause: returns parent as root
- Commit 5-decision chain: root cause traverses all 5

tests/integration/phase1/test_replay_integration.py:
- Commit original decision at policy v1.0.0
- Create policy v2.0.0 with lower confidence threshold
- Replay with policy_version=v2.0.0: detects oversight_threshold_changes
- Batch replay: 10 decisions, 3 would change outcome with new policy
- policy_impact_analysis: correct change rate on realistic dataset

tests/integration/phase1/test_drift_detection_integration.py:
- Insert 30 baseline decisions at avg confidence 0.90
- Insert 7 observation decisions at avg confidence 0.73 (policy threshold 0.85)
- Run detect_drift: HIGH severity confidence_threshold_drift detected
- Insert baseline exception_rate 0.05, observation exception_rate 0.15
- Run detect_drift: exception_rate_spike MEDIUM detected

tests/integration/phase1/test_workspace_isolation.py:
- Create workspace A and workspace B
- Commit 10 decisions to workspace A, 5 to workspace B
- Query with workspace A key: returns exactly 10 decisions
- Query with workspace B key: returns exactly 5 decisions
- Workspace A key cannot access workspace B routes: 403
- Cross-workspace chain verify: only sees own records

tests/integration/phase1/test_article12_monitoring.py:
- Insert 50 decisions with mix of drift conditions
- Generate Article 12 report: risk_assessment = "significant_risks_require_review"
- Insert corrective action: overdue count decreases
- Run scheduler drift_scan: MonitoringEvent created for critical signal

tests/integration/phase1/test_audit_package.py:
- Generate full audit package: contains all components
- Verify package_hash: recompute and confirm match
- Generate ZIP: contains all 8 expected files
- Legal hold: verify no archiving occurs while hold is active
```

---

## ══════════════════════════════════════════════════════════════
## PROMPT P1-11 — Phase 1 README + Documentation Update
## ══════════════════════════════════════════════════════════════

**Session goal:** Update all documentation to reflect Phase 1 capabilities. This is what design partners and early customers read.

```
[PASTE GLOBAL CONTEXT ABOVE FIRST]

TASK: Update README.md and add docs/ directory with Phase 1 documentation.

═══ README.md updates ═══

Add Phase 1 to the "What DAI Records" section showing authority_chain_id
and parent_decision_id fields in the YAML example.

Add new sections:

## 🔗 Policy Versioning
Short explanation + example:
  dai policy create → dai policy diff 1.0.0 2.0.0 → dai policy resolve --at 2026-01-15T09:00:00Z

## ⛓️ Decision Lineage
Short explanation + example:
  .caused_by(parent_decision_id="...", edge_type="escalated_from")
  dai lineage --decision-id {...}

## 🔁 Decision Replay
Short explanation + example:
  POST /decisions/{id}/replay with policy_version substitution
  ReplayResult showing outcome_changed=True, OutcomeDiff

## 📊 Policy Drift Detection
Short explanation of what drift means + example DriftSignal output

## 🔐 Workspaces & RBAC
Table: Workspace roles and permissions

## 📋 Article 12 Monitoring
What it covers beyond Article 19, how to generate.

Update Roadmap table:
Phase 0: Done (as before)
Phase 1: Done — all 8 pillars listed

═══ docs/ directory ═══

docs/policy-versioning.md
  Full guide to PolicyStore, PolicyVersion lifecycle, resolve_at,
  diff, ExceptionReasonRegistry. Include real insurance example.

docs/authority-chains.md
  Full guide to AuthorityChain, AuthorityNode, delegation validation,
  violation detection. Include claims authority hierarchy example.

docs/decision-lineage.md
  Full guide to lineage edges, graph building, root cause analysis.
  D3.js visualisation JSON format.

docs/decision-replay.md
  Full guide to ReplayRequest, variables, ReplayResult interpretation,
  batch replay, policy impact analysis.

docs/drift-detection.md
  Full guide to DriftSignal types, severity thresholds, OverrideCluster,
  ConsistencyReport. How to integrate with CI/CD.

docs/compliance.md
  Combined Article 9, 12, 13, 14, 17, 18, 19 coverage map.
  Table: EU AI Act Article → DecisionLedger feature → how to verify.

docs/workspaces.md
  Workspace setup, API key management, RBAC, multi-tenant architecture.

docs/audit-package.md
  How to generate, what is included, package_hash verification,
  ZIP format contents, legal hold.
```

---

## ══════════════════════════════════════════════════════════════
## EXECUTION ORDER SUMMARY — PHASE 1
## ══════════════════════════════════════════════════════════════

Run prompts in this exact order. Each depends on the previous.

| # | Prompt | Key output | Estimated time |
|---|--------|------------|----------------|
| P1-01 | Policy Version Store | dai/policy/ + /policies routes | 60 min |
| P1-02 | Authority Chain | dai/authority/ + /authority-chains routes | 60 min |
| P1-03 | Decision Lineage | dai/lineage/ + /lineage routes | 50 min |
| P1-04 | Decision Replay | dai/replay/ + /replay routes | 90 min |
| P1-05 | Drift Detection | dai/intelligence/ + /intelligence routes | 90 min |
| P1-06 | Workspace RBAC | Cross-cutting auth refactor + /workspaces | 90 min |
| P1-07 | Article 12 Monitoring | monitoring/ + scheduler + /monitoring routes | 60 min |
| P1-08 | Retention & Audit Package | Retention jobs + /export/audit-package | 60 min |
| P1-09 | CLI Extensions | 10 new CLI commands | 60 min |
| P1-10 | Integration Tests | tests/integration/phase1/ | 90 min |
| P1-11 | Documentation | README + docs/ | 45 min |

**Total estimated time with Copilot: 12–14 hours across sessions.**

---

## ══════════════════════════════════════════════════════════════
## PHASE 1 VERIFICATION CHECKLIST — Run after all prompts complete
## ══════════════════════════════════════════════════════════════

```bash
# Type checking — must pass clean including new modules
mypy dai/ dai_server/ cli/ --strict

# Linting
ruff check dai/ dai_server/ cli/ tests/

# Full test suite — unit + integration
pytest tests/ -v --cov=dai --cov=dai_server --cov-report=term-missing
# Target: ≥ 90% coverage maintained

# Phase 1 specific integration tests
pytest tests/integration/phase1/ -v

# Policy lifecycle end-to-end
python -c "
import asyncio
from dai.policy.store import PolicyStore
# Create v1 → create v2 → resolve at v1 time → confirm returns v1
"

# Authority chain validation
python -c "
from dai.authority.chain import AuthorityChainBuilder, validate_decision_against_chain
# Build 3-node chain, validate low-confidence decision, confirm violation
"

# Drift detection on synthetic data
python scripts/generate_drift_scenario.py  # creates 30 baseline + 7 drifted records
dai intelligence drift --agent test-agent --type claims_triage
# Expected: ≥ 1 HIGH severity drift signal

# Workspace isolation
python scripts/smoke_test_workspaces.py  # creates 2 workspaces, confirms isolation

# Full audit package
dai audit-package --from 2026-01-01 --to 2026-12-31 --format zip
# Expected: 8 files in ZIP, package_hash valid

# Article 12 report generation
curl -X POST "http://localhost:8080/export/article12" \
  -H "X-API-Key: $DAI_API_KEY" \
  -d '{"from_timestamp": "2026-01-01T00:00:00Z", "to_timestamp": "2026-12-31T23:59:59Z"}'
# Expected: Article12Report JSON with risk_assessment field populated

# Replay engine
curl -X POST "http://localhost:8080/decisions/$DECISION_ID/replay" \
  -H "X-API-Key: $DAI_API_KEY" \
  -d '{"variables": [{"variable_type": "policy_version", "original_value": "3.1.0", "substituted_value": "3.2.0", "description": "Testing policy update impact"}], "replay_reason": "policy_update_impact", "requested_by": "engineering-lead"}'
# Expected: ReplayResult with outcome_diffs

# New PyPI release
python -m build
# Bump to version 0.2.0 in pyproject.toml before build
# Expected: dist/decision_ledger_sdk-0.2.0.tar.gz
```

---

## ══════════════════════════════════════════════════════════════
## EU AI ACT COMPLIANCE COVERAGE MAP — Phase 0 + Phase 1
## ══════════════════════════════════════════════════════════════

| Article | Requirement | Phase 0 Coverage | Phase 1 Coverage |
|---|---|---|---|
| Art. 9 | Risk management system | Partial (decision logging) | ✅ Full (drift detection, continuous monitoring, corrective actions) |
| Art. 10 | Data governance | ✅ Evidence refs logged | ✅ Policy version governance |
| Art. 11 | Technical documentation | Not in scope | Audit package covers |
| Art. 12 | Record-keeping / post-market monitoring | Partial | ✅ Full Article 12 report + scheduler |
| Art. 13 | Transparency to deployers | ✅ Decision records queryable | ✅ Policy diff, authority chain visible |
| Art. 14 | Human oversight mechanisms | ✅ Override recording | ✅ Override clustering, authority validation |
| Art. 17 | Quality management system | Not in scope | ✅ Workspace RBAC + monitoring |
| Art. 18 | Documentation keeping | Not in scope | ✅ Retention policy (10yr for policy docs) |
| Art. 19 | Automatically generated logs | ✅ Full | ✅ Full + lineage + replay |
| Art. 20 | Corrective actions | Not in scope | ✅ Corrective action recording + tracking |
```
