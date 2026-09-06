# Nutrition Agent Safety Policy

Status: Canonical Phase 0 safety contract for implementation.

Policy version: `nutrition-safety-v1`.

This is the sole authority for Nutrition Agent trigger codes, ordering, thresholds, phrase families, user-safe projections, and persistence behavior. The master implementation plan must link here rather than duplicate this matrix. Changes require a dated decision in `docs/nutrition_agent/NUTRITION-SERVICE-IMPLEMENTATION-PLAN.md` Section 14, an API/data-compatibility assessment, and updated regression tests.

## Binding principles

- Safety evaluation runs before assessment presentation, target calculation/save, and meal planning. Escalation is deterministic and never calls the LLM.
- The agent must not diagnose, treat, prescribe medication or supplement dosing, or provide prescriptive calorie-deficit/meal-plan guidance for escalation outcomes.
- Required disclaimers are preserved in deterministic and LLM presentation paths.
- Raw medical disclosures, free-form risk details, meal descriptions, food queries, source phrase matches, prompts, reasoning, and tool traces are never stored in safety history, logs, metrics, or public projections.

## Structured safety context

`SafetyContext` is optional, request-scoped, and may be supplied to assessment, target calculation/save, and meal-plan generation. Unknown values return `422 VALIDATION_ERROR`; `unknown` never suppresses a message-derived finding.

- `pregnancy_lactation_status`: `unknown`, `not_pregnant_or_breastfeeding`, `pregnant`, `breastfeeding`, `pregnant_and_breastfeeding`.
- `medical_conditions`: deduplicated list, maximum 6: `diabetes`, `uses_insulin_or_glucose_lowering_medication`, `kidney_disease`, `heart_disease`, `hypertension`, `eating_disorder_history`.
- `risk_flags`: deduplicated list: `under_18`, `current_disordered_eating_behaviors`, `chest_pain_or_breathing_difficulty`, `fainting_or_severe_dizziness`, `purging_or_laxative_use`, `severe_food_restriction`, `rapid_weight_loss_request`, `other_medical_condition`.

## Stable trigger codes and detection

Combine structured and normalized Unicode case-folded message findings, deduplicate them, and return/persist them only in this order. Literal phrase matching uses word boundaries where applicable; the source phrase is never retained.

| Order | Code | Deterministic signal |
| --- | --- | --- |
| 1 | `CHEST_PAIN_OR_BREATHING_DIFFICULTY` | Structured chest/breathing flag; `chest pain`, `shortness of breath`, or `trouble breathing`. |
| 2 | `FAINTING_OR_SEVERE_DIZZINESS` | Structured flag; `fainting`, `passed out`, or `severe dizziness`. |
| 3 | `PURGING_OR_LAXATIVE_USE` | Structured flag; `purging` or `laxative`. |
| 4 | `SEVERE_FOOD_RESTRICTION` | Structured flag; `severely restrict` or `starving myself`. |
| 5 | `CURRENT_DISORDERED_EATING_BEHAVIORS` | Structured flag. |
| 6 | `EATING_DISORDER_HISTORY` | Structured condition; `eating disorder`, `anorexia`, `bulimia`, or `binge eating`. |
| 7 | `PREGNANCY_OR_BREASTFEEDING` | Positive pregnancy/lactation enum; `pregnant`, `pregnancy`, or `breastfeeding`. |
| 8 | `DIABETES_OR_INSULIN` | Diabetes/glucose-lowering condition; `diabetes`, `diabetic`, or `insulin`. |
| 9 | `KIDNEY_DISEASE` | Kidney condition; `kidney disease` or `renal disease`. |
| 10 | `HEART_DISEASE_OR_HYPERTENSION` | Heart/hypertension condition; `heart disease`, `heart condition`, `high blood pressure`, or `hypertension`. |
| 11 | `UNDER_18` | Structured `under_18` flag or required target/plan input age below 18. |
| 12 | `RAPID_WEIGHT_LOSS_REQUEST` | Structured flag or a requested weekly loss greater than 1% of current body weight. The comparison is available only when positive `weight_kg` and requested weekly loss are both supplied; otherwise no inferred numerical finding is made. |
| 13 | `OTHER_MEDICAL_CONDITION` | Structured flag; `dehydrate`, `water cut`, or `rapid water loss`; active anaphylaxis/allergic-reaction language; or medication, drug, or supplement dosage/advice requests. |
| 14 | `BMI_UNDERWEIGHT` | BMI below 18.5. |
| 15 | `BMI_CLASS_III_OBESITY` | BMI at or above 40.0. |
| 16 | `BELOW_MINIMUM_CALORIE_FLOOR` | Proposed/recommended calories below the applicable floor. |

Food allergies alone are not a trigger. Meal planning must exclude recorded allergies/restrictions; if a safe exclusion cannot be made, refuse the plan using `OTHER_MEDICAL_CONDITION` without exposing the allergy text.

## Outcomes and calorie floors

Codes 1–13 produce `status="escalate"`, `score=10`, ordered `SafetyFinding` values with `severity="escalate"`, and block target calculation/save, meal-plan generation, optional LLM presentation, and prescriptive nutrition guidance.

Deterministic referral text:

> I can’t provide a nutrition target or meal plan for this situation. Please seek personalized guidance from a qualified healthcare professional; seek urgent medical care or local emergency services if symptoms are severe or immediate.

For codes 3–6, append:

> If this relates to disordered eating or feeling unsafe around food, consider contacting a qualified clinician or an eating-disorder support service in your region.

Codes 14–16 do not automatically escalate. They require `red` or safer non-prescriptive handling and recommendation to seek qualified professional support. Target save must reject a result below the applicable floor: female `1200 kcal/day`, male `1500 kcal/day`, other/unknown `1200 kcal/day`.

## LLM, persistence, and regression requirements

- Non-escalation LLM input is limited to structured, non-sensitive assessment data. Post-validate output for the required disclaimer, diagnosis/treatment language, prompt/secret disclosure, and contradiction of deterministic status; otherwise use deterministic presentation.
- Final user-facing output includes: “All nutrition advice is for general informational purposes only and does not constitute medical advice. Consult a healthcare provider before making significant dietary changes.”
- Assessment history may retain only policy version, status, score, ordered codes, non-sensitive escalation projection, target summary, sanitized recommendations, and timestamp. Public history/chat projections never expose raw context, source text, reasoning, or tool traces.
- Tests cover unknown enum rejection; every row above; order/deduplication; >1%-of-body-weight calculation; allergy exclusion/refusal; escalation blocking all mutations and LLM calls; disclaimer fallback; and privacy-safe persistence.

## Changelog

| Policy version | Date | Change | Required regression coverage |
| --- | --- | --- |
| `nutrition-safety-v1` | 2026-08-30 | Initial unified deterministic safety contract | Full matrix and privacy/LLM regression requirements above |