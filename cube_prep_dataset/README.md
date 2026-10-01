# CUBE Prep Manager — Main Image Dataset

100 unique synthetic units × 3 views = 300 controlled images.

The CSV preserves the organiser `prep_sample.csv` columns first and adds:
product_category, scenario, expected_overall_status, expected_issue_explanation, evidence_view, image_quality_class, split.

Coverage includes every repository outcome vocabulary and named failure/ambiguity scenario:
- PASS / FAIL / UNCERTAIN
- polybag: yes / not_sealed / missing / uncertain / not_required
- warning: legible / obscured_by_fold / missing / uncertain / not_required
- FNSKU: flat / on_seam / on_curve / on_edge / missing / uncertain
- original barcode: yes / no / uncertain
- expiry: legible / illegible_after_wrap / uncertain / not_required
- handling: all_present / some_missing / uncertain / not_required

Split:
train 70 units, validation 15, heldout development test 15. Splits are by unit, not by image.

IMPORTANT:
The organiser explicitly states that its sample CSV is dummy data, must not be trained on, and that participants must create their own fixtures/evaluation set. This dataset is a controlled development fixture, not the organiser's hidden 50-unit evaluation set.

The organiser also states that prep-center economics are $0.40-$1.10 per unit and the cost per check has to fit inside that range. `prep_price_usd` is retained for runtime economics calculations. `unit_economics.csv` contains only a clearly labelled prototype target assumption, not an organiser-defined metric.

For final evaluation, use a genuinely unseen, independently labelled real-photo set and report per-check precision/recall/F1, false positives, false negatives, UNCERTAIN rate, named failure modes, evidence quality and latency/cost.
