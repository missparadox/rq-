# Evaluation Standard

Use this reference only for explicit full-context review. Split packets embed
the compact scoring standard required for their single OR.

## Score Structure

| Scope | Dimension | Weight |
| --- | --- | ---: |
| OR | OR-用户语言描述 | 12 |
| OR | OR-应用场景 | 12 |
| OR | OR-用户价值 | 10 |
| OR | OR-约束和限制 | 6 |
| DR | DR-安全分析 | 5 |
| DR | DR-技术描述 | 10 |
| DR | DR-可测试性 | 10 |
| DR | DR-无歧义性 | 8 |
| DR | DR-异常描述 | 7 |
| OR + DR | 需求分解完整性 | 7 |
| OR + DR | 需求分解边界清晰度 | 6 |
| OR + DR | 需求映射一致性 | 7 |

- Score each OR statement once out of `40`.
- Score each linked DR separately out of `40`; the DR portion is their arithmetic average.
- Score OR-to-DR decomposition once out of `20`.
- OR total = OR portion + DR average + decomposition portion.
- Document total = arithmetic average of all OR totals.

## Evidence Rules

- Judge only explicit evidence in the current OR, its linked DRs, and packetized supporting fields.
- Every dimension must have a numeric score. Do not use `N/A`, `null`, or omit a dimension.
- If a value, scenario, constraint, verification method, or failure behavior is not stated, score the gap rather than inferring intent.
- Treat unresolved external references, figures, or “如下图” text as missing evidence.
- Use a short evidence-based reason per dimension.
- OR dimensions use only OR core fields and OR additional fields. DR details must not raise OR dimension scores; DR evidence is used only for DR dimensions and OR-to-DR decomposition or traceability dimensions.
- OR-用户语言描述 evaluates whether the OR expresses the request in requirement-side language that non-technical stakeholders can understand. If the OR is mainly technical implementation or solution detail and the requirement meaning must be inferred from that implementation, cap this dimension at `<= 6/12`.
- OR-约束和限制 evaluates whether the OR states the boundary conditions under which the requirement applies. If the OR describes only functional capability with no scope, prerequisite, or limitation, cap this dimension at `<= 2/6`.

## Dimension Anchors

| Dimension | Meets | Weak | Missing |
| --- | --- | --- | --- |
| OR-用户语言描述 | User or business need is clear. | Technical statement but need is inferable. | User-side need cannot be identified. |
| OR-应用场景 | Actor, trigger, environment, or business context is explicit. | Function is clear but scenario incomplete. | Abstract capability only. |
| OR-用户价值 | User problem, business value, or compliance motivation is explicit. | Value is only inferable. | Functional or technical wording only. |
| OR-约束和限制 | Scope, exclusions, compatibility, compliance, deployment, or runtime limits are explicit. | Constraint is mentioned but boundary is incomplete. | No constraint information. |
| DR-安全分析 | Relevant authentication, authorization, audit, encryption, or safety control is explicit. | Generic security statement only. | Security-relevant behavior has no control requirement. |
| DR-技术描述 | Behavior, inputs/outputs, conditions, and main processing are clear. | Key parameter, state, boundary, or result is missing. | Only vague “支持/提供/实现” wording. |
| DR-可测试性 | Tests or acceptance steps derive directly from stated input/action/result. | Testable only with additional assumptions. | Cannot derive verification points. |
| DR-无歧义性 | Parameters, scope, states, quantities, or results are precise. | Important boundaries allow multiple readings. | Broad wording without definition. |
| DR-异常描述 | Failure triggers and expected handling are explicit. | Some exception behavior is stated but incomplete. | Happy path only. |
| 需求分解完整性 | DRs cover all key OR capabilities. | Main capability covered with gaps. | Key OR capability has no DR landing point. |
| 需求分解边界清晰度 | DR responsibilities are clear and non-overlapping. | Some overlap or unclear ownership. | Boundaries are unusable. |
| 需求映射一致性 | OR and DR scope/meaning agree. | Partial drift or weak mapping. | Contradiction or untrustworthy mapping. |

## Red-Line Caps

| Rule | Trigger | Cap |
| --- | --- | --- |
| R1 | OR does not explicitly state user value, business purpose, or compliance/market motivation. | OR portion `<= 24/40` |
| R2 | A DR does not directly yield test points, acceptance conditions, or verification steps. | That DR `<= 24/40` |
| R3 | A DR only uses vague wording such as “支持/提供/实现” without key behavioral detail. | That DR `<= 20/40` |
| R4 | An OR has obviously uncovered key sub-capabilities. | Decomposition portion `<= 10/20` |
| R5 | DRs are obviously duplicated, conflicting, or not traceable back to the OR. | Decomposition portion `<= 8/20` |

When a red line triggers, identify its rule ID and cap basis in the result.

## Full-Context Review Procedure

1. Identify each scored OR and all of its linked DRs from the expanded packet.
2. Score the OR once, each DR once, and the OR-to-DR decomposition once.
3. Apply the anchors and red-line caps before finalizing each OR result.
4. Produce the report using `report-template.md`. All scored OR units must
   participate in totals, grade distribution, category statistics, and the
   full OR summary table. Only expand detailed OR evaluations for the
   five lowest-scoring ORs and the single highest-scoring OR. If the selected
   sets overlap, do not duplicate the OR. For ties, keep the original OR order.
   Do not include revision-action sections unless explicitly requested.

## Quality Signals

Positive signals include explicit actor/trigger, stated value, defined ranges
or defaults, directly derivable acceptance checks, security/audit controls,
failure handling, and coherent OR-to-DR mapping.

Negative signals include broad “支持” wording, standards cited without mapped
behavior, missing test points, missing failure behavior, external figure
dependencies, uncovered OR capabilities, and conflicting DRs.
