# DDC Migration Planning Rules

Rules are ordered by priority. Apply all applicable rules before submitting a plan.

## Rule 1 — Prefer content widget over raw_html

Always choose the `content` widget for text-based content unless the visual goal
is provably impossible with the WYSIWYG editor. Pages must remain client-editable
after migration. `raw_html` is a technical escape hatch, not a default.

Justify in the `intent` field when using raw_html. A plan that uses raw_html
without justification will be rejected by the verifier.

Rationale: discovered after a run where the model chose raw_html for all sections,
breaking client editability.

## Rule 2 — Collapse adjacent same-type empty sections

If two or more adjacent sections share the same sectionName and there is no
semantic reason to separate them (no visual break, no thematic shift), merge them
into one section with multiple widgets stacked inside.

Rationale: discovered after a run where redundant adjacent sections doubled API
calls with no visual benefit.

## Rule 3 — Never recreate map-hours with empty sections

`map-hours` is pre-wired. It ships with the map, contact info, and hours widgets
already configured. Using `empty-fifty-fifty` plus manual widget injection to
achieve the same result is always wrong.

Rationale: pre-wired sections have default widget preferences tuned for the
dealership context. Manual recreation loses those defaults.

## Rule 4 — Order sections top-to-bottom

The `position` field in each SectionPlanItem must reflect the visual top-to-bottom
order of the section on the source page. Position 0 is the topmost section.
