# Research Synthesis Reference

Use this reference only when the user needs research-level judgment, not for ordinary lookup or write routing.

## Adaptive Research Modes

Choose the lightest mode that can answer well:

- **Light lookup**: search, inspect candidates, report sources and coverage limits.
- **Synthesis**: combine read sources into a coherent topic summary with evidence anchors.
- **Research judgment**: evaluate an idea, direction, claim, novelty, risk, or literature support. Search for both support and counter-evidence.
- **Writing/output**: if the user asks to save the result, return to the main skill's write routing.

## Research Question Framing

For substantial judgment tasks, first restate the user's request as one core research question. If useful, decompose it into 2-6 lightweight units:

- **Subclaims**: assertions that need evidence.
- **Competing hypotheses**: plausible explanations that could both be true before reading.
- **Tensions**: pairs such as elicitation vs capability acquisition, external memory vs parameterized skill, project intuition vs paper evidence, or method gain vs evaluation artifact.

Use this framing to guide search and reading. Keep it internal for simple tasks; expose it only when it clarifies the answer or saved note. Do not force a hypothesis matrix for casual brainstorming.

## From Notes to Research Claims

Treat Notion, LLM Wiki, and Obsidian ideas as research material, not settled evidence. Convert useful notes into:

- claim;
- assumption;
- possible evidence;
- missing evidence;
- experiment implication;
- related literature to search.

Recent Notion pages are strong evidence of the user's current focus, not proof that a research claim is true. LLM Wiki pages are compiled memory and retrieval maps; use them to find sources and prior synthesis, but verify central claims against source-traceable material before treating them as evidence. Older Obsidian notes may be valuable as recurring questions, prior attempts, constraints, or alternative framings.

## Tentative vs Stable Claims

Keep claim status explicit when it matters:

- **Current project state**: what the user appears to be focusing on now, usually from recent Notion or recent notes.
- **Working hypothesis**: a plausible idea that guides search or experiments but is not settled evidence.
- **Stable knowledge**: a durable concept or summary supported well enough to save as reusable knowledge.
- **Evidence audit**: a stricter pass where every central claim needs anchors and coverage limits.

Do not over-stabilize ideas when writing to Obsidian. If a conclusion is mainly from project notes, LLM Wiki synthesis, or current inference, mark it as a working hypothesis or current framing. Notion project outputs can be more current-state oriented, but should still preserve important uncertainty and source anchors.

## Claim-Evidence Matrix

For research judgment tasks, organize internally around a lightweight matrix and expose it when useful:

- `Claim / hypothesis`: what is being judged.
- `Supporting evidence`: papers, notes, or project pages that support it.
- `Counter-evidence`: papers, notes, or observations that challenge it.
- `Source type`: paper evidence, personal note, project state, or current inference.
- `Confidence / gap`: what can be concluded and what could change the conclusion.

Use confidence labels:

- **High confidence**: supported by full paper evidence or multiple independent sources that agree.
- **Medium confidence**: supported by personal notes/project state or partial paper evidence, but not fully checked.
- **Low confidence**: mainly current inference, weak evidence, or needs another search/read pass.

## Counter-Evidence and Saturation

For research judgments, look for what would weaken the answer, not only what supports it. This is especially important for novelty, risk, contribution, "is this worth doing?", and literature-support questions.

Use judgment, not a mechanical checklist:

- Search for counter-evidence, competing methods, adjacent terms, older canonical work, and evaluation artifacts when they could change the answer.
- Treat "I did not find counter-evidence in this pass" as a scoped result, not proof that none exists.
- Continue searching when evidence is one-sided, comes only from personal notes/project state, lacks recent project context, lacks older high-level/canonical context, or misses the obvious adjacent literature.
- Stop when the evidence is sufficient for the user's task, not when every possible source has been exhausted. State the remaining uncertainty instead of over-searching.
- If the task is exploratory or time-boxed, prefer a useful provisional judgment plus clear next searches.

## Paper Role Assignment

When reviewing Zotero candidates, assign each important paper a research role instead of only listing it:

- **Framing/foundation**: defines the problem or paradigm.
- **Supporting evidence**: backs the user's claim or direction.
- **Counter-evidence**: challenges the claim or exposes limits.
- **Method reference**: provides a method, recipe, or implementation pattern.
- **Evaluation/metric reference**: provides tests, metrics, or analysis methods.
- **Terminology source**: gives language for naming the idea.
- **Adjacent analogy**: is not directly about the topic but may transfer useful structure.

## Handling Conflicts

When sources disagree, do not flatten the disagreement into a single averaged claim. First classify the conflict:

- **Time evolution**: recent material reflects current focus while older notes preserve previous attempts.
- **Framing difference**: sources use different terms or abstractions for related ideas.
- **Evidence-strength difference**: one side is paper evidence, the other is project intuition or a partial read.
- **Method/evaluation mismatch**: methods appear to conflict because they optimize different metrics, tasks, or settings.
- **True contradiction**: two sources make incompatible claims under comparable assumptions.

Expose the conflict only as much as needed. For daily synthesis, a short paragraph is enough. For novelty/risk/evidence-audit tasks, make the disagreement and what would resolve it explicit.

## Output Shape

For research judgment tasks, prefer this structure when it helps:

- `Research question`: the user's request restated as a research question.
- `Reading scope`: searched concepts, inspected workspaces, and read depth.
- `Evidence map`: key claims/tensions with support and counter-evidence.
- `Synthesis / judgment`: the integrated view and confidence.
- `Gaps / next searches`: missing literature, experiments, or analysis that could change the judgment.

For normal daily research use, do not cite every sentence. Anchor only central, contested, or reusable claims. For rigorous literature reviews or evidence audits, increase citation density and anchor every core claim.
