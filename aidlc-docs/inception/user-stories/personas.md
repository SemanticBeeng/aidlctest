# Personas

## Persona 1: Budget Shopper (Primary)

### Profile
- **Name**: Maya
- **Context**: Cost-conscious iOS user managing weekly household shopping
- **Goal**: Minimize spend while meeting dietary and quality constraints
- **Behavior**: Uses iterative multi-turn refinement, tracks pantry and recurring items

### Needs
- Budget-aware substitutions and prioritization
- Reuse of long-term preferences without re-entering details
- Clear alerts when recommendations rely on stale context
- Visibility into whether assistant has enough data for reliable planning

### Pain Points
- Repeating same preferences every session
- Drift in recommendations over long conversations
- Lack of confidence in whether model understanding is still current

---

## Persona 2: Event Shopper (Secondary)

### Profile
- **Name**: Arjun
- **Context**: iOS user planning shopping for events over several days
- **Goal**: Build and refine event-specific baskets under shifting constraints
- **Behavior**: Multi-session planning, changing guest counts and category priorities

### Needs
- Persistent event context across sessions
- Fast adaptation when event requirements change
- Explainable recommendations and rationale
- Automatic escalation to server for complex optimization

### Pain Points
- Losing context between sessions
- Inconsistent recommendations after many edits
- Difficulty knowing when to provide more data vs when model needs retraining

---

## Persona-to-Feature Priority
- **Budget Shopper**: budget optimization, pantry continuity, data sufficiency indicator, fine-tuning trigger insights
- **Event Shopper**: event thread persistence, context checkpointing, context-rot recovery, explainability
