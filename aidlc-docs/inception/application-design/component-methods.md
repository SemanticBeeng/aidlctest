# Component Methods

## C01 Mobile App Client
- `submitPlanningPrompt(request: PlanningPromptRequest): PlanningResponseView`
- `submitRefinementTurn(request: RefinementTurnRequest): PlanningResponseView`
- `displayReadinessState(state: ReadinessStateView): Unit`
- `displayRoutingDecision(decision: RoutingDecisionView): Unit`

## C02 On-Device Inference Adapter
- `inferOnDevice(request: InferenceRequest): InferenceResult`
- `estimateOnDeviceConfidence(result: InferenceResult): ConfidenceScore`
- `collectOnDeviceRuntimeMetrics(requestId: String): RuntimeMetrics`

## C03 Routing Policy Engine
- `decideRoute(context: RoutingContext): RoutingDecision`
- `evaluateRoutingPolicy(input: RoutingPolicyInput): PolicyEvaluationResult`
- `explainRoutingDecision(decision: RoutingDecision): DecisionExplanation`

## C04 Server Inference Gateway
- `inferOnServer(request: InferenceRequest): InferenceResult`
- `normalizeBackendResponse(raw: BackendRawResponse): InferenceResult`
- `handleServerFallbackFailure(error: BackendError): InferenceFailureResult`

## C05 Memory & Context Store
- `loadUserMemory(userId: String): UserMemoryProfile`
- `saveUserMemory(update: UserMemoryUpdate): SaveResult`
- `loadSessionContext(sessionId: String): SessionContext`
- `saveContextCheckpoint(checkpoint: ContextCheckpoint): SaveResult`
- `repairConflictedMemory(input: MemoryRepairInput): MemoryRepairResult`

## C06 Context-Rot Detector
- `computeContextRotScore(context: ContextSnapshot): ContextRotScore`
- `detectContextRotSignals(context: ContextSnapshot): ContextRotSignals`
- `suggestRecoveryAction(signals: ContextRotSignals): RecoveryAction`

## C07 Data Sufficiency Assessor
- `assessReadiness(input: ReadinessInput): ReadinessAssessment`
- `identifyDataGaps(input: ReadinessInput): List<DataGap>`
- `buildGuidedDataQuestions(gaps: List<DataGap>): GuidedQuestionSet`

## C08 Fine-Tuning Signal Evaluator
- `evaluateFineTuningSignal(input: FineTuningSignalInput): FineTuningSignal`
- `buildFineTuningEvidence(input: FineTuningSignalInput): FineTuningEvidence`

## C09 Evaluation & Telemetry Collector
- `recordRoutingEvent(event: RoutingTelemetryEvent): Unit`
- `recordPolicyEvaluation(event: PolicyTelemetryEvent): Unit`
- `recordQualityMetrics(event: QualityMetricsEvent): Unit`
- `fetchEvaluationWindow(query: EvaluationQuery): EvaluationWindowSummary`

## Shared Method Contract Notes
- Method contracts are high-level and implementation-agnostic.
- Domain rules and algorithm details are deferred to Functional Design stage.
- Kotlin interfaces are recommended for ports/adapters.
