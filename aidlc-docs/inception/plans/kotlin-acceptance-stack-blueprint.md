# Kotlin Acceptance Stack Blueprint

## Goal
Provide a concrete Kotlin-based implementation pattern for acceptance criteria style Option X:
- Gherkin for behavior flow
- Decision tables for routing/memory thresholds
- YAML policy DSL for context-rot, data sufficiency, and fine-tuning triggers

## Suggested Stack

### Core Frameworks
- Kotlin 1.9+
- JUnit 5
- Cucumber JVM (`cucumber-java`, `cucumber-junit-platform-engine`)
- Cucumber Kotlin step support (`cucumber-kotlin`)
- Kotest (optional assertions and data-driven checks)

### Serialization and DSL Parsing
- `kotlinx.serialization`
- YAML parser: `kaml` or `SnakeYAML`

### Optional Policy Evaluation
- In-process Kotlin policy evaluator (recommended MVP)
- Optional OPA/Rego integration later for externalized policies

## Gradle Dependencies (Kotlin DSL)
```kotlin
dependencies {
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.2")
    testImplementation("io.cucumber:cucumber-java:7.18.0")
    testImplementation("io.cucumber:cucumber-junit-platform-engine:7.18.0")
    testImplementation("io.cucumber:cucumber-kotlin:7.18.0")
    testImplementation("io.kotest:kotest-assertions-core:5.9.1")

    implementation("org.jetbrains.kotlinx:kotlinx-serialization-core:1.7.1")
    implementation("com.charleskorn.kaml:kaml:0.58.0")
}

tasks.test {
    useJUnitPlatform()
}
```

## Recommended Folder Layout
```text
acceptance/
  features/
    shopping_routing.feature
  stepdefs/
    ShoppingRoutingSteps.kt
  tables/
    routing-thresholds.csv
  policies/
    context-policy.yaml
  fixtures/
    session-context.json

src/main/kotlin/com/example/assistant/
  acceptance/
    PolicyModels.kt
    PolicyEngine.kt
    RoutingDecisionService.kt
  memory/
    MemoryFreshnessService.kt
    ContextRotDetector.kt
```

## Sample 3-Part Acceptance Specification

### 1) Gherkin Scenario
```gherkin
Feature: Hybrid routing with context reliability

  Scenario: Route to server when context rot is high and confidence is low
    Given a user session with memory age "10d"
    And user data sufficiency is "partial"
    And on-device confidence is "0.54"
    When the assistant evaluates routing policy
    Then route should be "server"
    And context integrity action should be "reconfirm_preferences"
    And fine-tuning recommendation should be "no"
```

### 2) Decision Table (routing-thresholds.csv)
```csv
confidence_min,context_age_days_max,rot_score_max,sufficiency,route,integrity_action
0.70,7,0.35,sufficient,device,none
0.62,7,0.45,partial,device,checkpoint_summary
0.62,30,0.55,partial,server,reconfirm_preferences
0.55,30,0.60,insufficient,server,data_completion_flow
```

### 3) YAML Policy DSL (context-policy.yaml)
```yaml
version: 1
policies:
  routing:
    device_default: true
    server_fallback_when:
      - confidence < 0.62
      - context_age_days > 7
      - rot_score > 0.45

  data_sufficiency:
    sufficient_when:
      min_profile_fields: 8
      min_session_turns: 20
      min_successful_plans: 5

  fine_tuning_trigger:
    enabled: true
    requires_all:
      - eval_consistency_score < 0.82
      - repeated_failure_windows >= 3
      - data_sufficiency == "sufficient"
```

## Minimal Kotlin Model + Evaluation Skeleton
```kotlin
@kotlinx.serialization.Serializable
data class ContextPolicy(
    val version: Int,
    val policies: Policies
)

@kotlinx.serialization.Serializable
data class Policies(
    val routing: Routing,
    val data_sufficiency: DataSufficiency,
    val fine_tuning_trigger: FineTuningTrigger
)

@kotlinx.serialization.Serializable
data class Routing(
    val device_default: Boolean,
    val server_fallback_when: List<String>
)

@kotlinx.serialization.Serializable
data class DataSufficiency(
    val sufficient_when: SufficiencyThreshold
)

@kotlinx.serialization.Serializable
data class SufficiencyThreshold(
    val min_profile_fields: Int,
    val min_session_turns: Int,
    val min_successful_plans: Int
)

@kotlinx.serialization.Serializable
data class FineTuningTrigger(
    val enabled: Boolean,
    val requires_all: List<String>
)
```

## Adoption Notes
- Keep policy DSL declarative and versioned.
- Start with in-process evaluation for speed; migrate to OPA only when policy governance complexity increases.
- Use Gherkin only for behavior-critical flows; use tables/policy DSL for threshold-heavy logic.
- Treat acceptance artifacts as product contracts shared across product, ML, and engineering.

## Proposed Plan Answer Text
Use this in `story-generation-plan.md` under Acceptance Criteria Style:

`[Answer]: X Hybrid DSL — Gherkin (Given/When/Then) + Decision Tables for routing/memory thresholds + YAML Policy DSL for context-rot detection, data-sufficiency readiness, and fine-tuning trigger rules.`
