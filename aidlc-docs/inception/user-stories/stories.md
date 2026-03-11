# User Stories

## Story Organization Strategy
This story set follows the approved approach:
1. **Domain-first**: Electronics and Fashion shopping planning journeys
2. **Persona-second**: Budget Shopper and Event Shopper specific needs
3. **Feature-third**: Multi-turn conversation, routing, memory, recommendations, context integrity

## Acceptance Criteria Format Standard (Option X)
Each story uses:
- **Gherkin** for behavior flow
- **Decision rules table** for routing/memory thresholds
- **Policy checks** for context-rot, data sufficiency, and fine-tuning trigger behavior

---

## Epic E1: Electronics Planning

### US-01 Electronics Basket Initialization
**As a** Budget Shopper  
**I want** to describe my electronics shopping goals and constraints in one prompt  
**So that** the assistant generates a categorized starter basket on-device.

**Acceptance Criteria (Gherkin)**
- Given an iOS user with initial preference profile
- When the user asks for an electronics shopping plan
- Then the assistant returns a categorized starter basket
- And the first response is generated on-device when confidence threshold is met

**Decision Rules**
| Condition | Expected Result |
|---|---|
| Confidence >= device threshold and low rot risk | Route device |
| Confidence < device threshold | Route server |

**Policy Checks**
- Context integrity score must be recorded.
- Routing decision must be logged.

### US-02 Electronics Budget Optimization
**As a** Budget Shopper  
**I want** cheaper alternatives suggested without breaking core preferences  
**So that** I can stay within budget.

**Acceptance Criteria (Gherkin)**
- Given an existing electronics basket and budget cap
- When the user asks for budget optimization
- Then the assistant proposes substitutions ranked by savings impact
- And preserves non-negotiable constraints from memory

**Policy Checks**
- Data sufficiency state is shown (insufficient/partial/sufficient).
- If insufficient, assistant requests minimal missing fields.

### US-03 Electronics Context-Rot Recovery
**As a** Event Shopper  
**I want** the assistant to detect when recommendations drift after many refinements  
**So that** I can recover trustworthy planning context.

**Acceptance Criteria (Gherkin)**
- Given a long multi-turn electronics planning session
- When contradiction and staleness signals exceed policy thresholds
- Then assistant flags context rot
- And emits a checkpoint-based recovery prompt

**Policy Checks**
- Rot detection trigger recorded with contributing signals.
- Recovery action must be one of: checkpoint restore, reconfirm preferences.

---

## Epic E2: Fashion Planning

### US-04 Fashion Capsule List Creation
**As a** Event Shopper  
**I want** outfit-related shopping suggestions for a specific event context  
**So that** I can quickly compose a usable list.

**Acceptance Criteria (Gherkin)**
- Given event type, date, and budget range
- When user asks for fashion planning
- Then assistant generates a capsule list grouped by category
- And preserves event context across sessions

**Policy Checks**
- Session context key must persist across turns.

### US-05 Fashion Preference Memory Continuity
**As a** Budget Shopper  
**I want** style/brand constraints remembered between sessions  
**So that** I do not repeat preference setup every time.

**Acceptance Criteria (Gherkin)**
- Given user has saved preferences
- When a new session starts
- Then assistant applies stored preferences by default
- And asks only targeted confirmation when freshness window has expired

**Decision Rules**
| Memory Freshness | Action |
|---|---|
| Fresh | Use directly |
| Near-stale | Ask lightweight confirmation |
| Stale/conflicted | Run memory repair flow |

### US-06 Fashion Explainability
**As a** Event Shopper  
**I want** concise rationale for recommended items  
**So that** I can trust and adjust suggestions.

**Acceptance Criteria (Gherkin)**
- Given generated fashion recommendations
- When user asks why an item is included
- Then assistant returns rationale referencing constraints and goals
- And tags confidence level for each rationale

---

## Epic E3: Hybrid Inference and Reliability Features

### US-07 Hybrid Routing Transparency
**As a** shopper  
**I want** clear indication when the assistant uses device vs server path  
**So that** I understand behavior and latency changes.

**Acceptance Criteria (Gherkin)**
- Given a planning request
- When routing engine evaluates confidence and context signals
- Then route decision is surfaced with concise reason
- And audit metadata is persisted

### US-08 Data Sufficiency Readiness Indicator
**As a** shopper  
**I want** to know if my profile/history is sufficient for high-quality planning  
**So that** I can decide whether to provide more data.

**Acceptance Criteria (Gherkin)**
- Given current profile, session history, and success history
- When assistant computes readiness
- Then assistant shows insufficient/partial/sufficient status
- And provides next-best actions to improve readiness when needed

### US-09 Guided Data Completion Flow
**As a** shopper  
**I want** targeted follow-up questions only for missing high-impact fields  
**So that** I can improve plan quality efficiently.

**Acceptance Criteria (Gherkin)**
- Given readiness is insufficient or partial
- When user opts to improve readiness
- Then assistant asks prioritized minimal questions
- And updates readiness score after each answer

### US-10 Fine-Tuning Recommendation Trigger
**As a** product/ML stakeholder  
**I want** a policy-based signal for when fine-tuning is needed  
**So that** we do not overfit on sparse user data and only tune when justified.

**Acceptance Criteria (Gherkin)**
- Given repeated evaluation failures over configured windows
- And readiness state is sufficient
- When threshold conditions are met
- Then assistant emits fine-tuning recommendation flag
- And includes evidence summary (failure windows, metrics)

**Policy Checks**
- Fine-tuning recommendation must remain off when readiness is insufficient.
- Trigger criteria must be fully auditable.

### US-11 Context Checkpoint Management
**As a** shopper  
**I want** major plan milestones checkpointed  
**So that** the assistant can recover stable context after drift.

**Acceptance Criteria (Gherkin)**
- Given user confirms a milestone (budget, dietary, store choice)
- When milestone is saved
- Then checkpoint is available for restoration
- And later turns can reference checkpoint as canonical context

### US-12 Server Fallback for Complex Reasoning
**As a** shopper  
**I want** automatic server escalation for complex optimization queries  
**So that** I still get quality outputs when on-device capacity is insufficient.

**Acceptance Criteria (Gherkin)**
- Given user query exceeds on-device complexity/confidence envelope
- When routing policy evaluates request
- Then assistant routes to server backend (`llm-d`)
- And response returns with consistent UX and memory continuity

---

## Persona Mapping
| Story ID | Budget Shopper | Event Shopper |
|---|---|---|
| US-01 | Primary | Secondary |
| US-02 | Primary | Secondary |
| US-03 | Secondary | Primary |
| US-04 | Secondary | Primary |
| US-05 | Primary | Secondary |
| US-06 | Secondary | Primary |
| US-07 | Primary | Primary |
| US-08 | Primary | Primary |
| US-09 | Primary | Secondary |
| US-10 | Secondary | Secondary |
| US-11 | Secondary | Primary |
| US-12 | Primary | Primary |

## INVEST Verification Summary
- **Independent**: Stories scoped to testable behavior units.
- **Negotiable**: Implementation details left open while outcomes are fixed.
- **Valuable**: Each story targets a user or product outcome.
- **Estimable**: Story boundaries and acceptance checks are explicit.
- **Small**: Stories sized for incremental delivery.
- **Testable**: Gherkin + rule/policy checks provide validation paths.
