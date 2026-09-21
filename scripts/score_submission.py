#!/usr/bin/env python3
"""
Score submission.json with the organizers' official scorer.

The organizer package is NOT part of this repository (it contains the answer
key). Point these environment variables at your local copy:

    SHIPGUARD_GROUND_TRUTH   path to data_v2/ground_truth.json
    SHIPGUARD_SCORER         optional; folder holding scoring.py
                             (defaults to <ground truth>/../../server)

    python scripts/score_submission.py
    python scripts/score_submission.py path/to/submission.json

Numbers come from the organizers' `scoring.score_all`, never from a local
reimplementation, so they stay authoritative. This script reads the ground
truth only to compute aggregate metrics — it never prints per-email labels.
"""

import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]

GROUND_TRUTH_ENV = "SHIPGUARD_GROUND_TRUTH"
SCORER_ENV = "SHIPGUARD_SCORER"


def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def resolve_ground_truth():
    value = os.getenv(GROUND_TRUTH_ENV)

    if not value or not value.strip():
        fail(
            f"{GROUND_TRUTH_ENV} is not set.\n"
            "  The organizer package lives outside this repository because it\n"
            "  contains the answer key. Set the variable to its\n"
            "  data_v2/ground_truth.json, for example:\n"
            '    $env:SHIPGUARD_GROUND_TRUTH = '
            '"D:\\Coding\\sdoc-hackathon-docker\\data_v2\\ground_truth.json"'
        )

    path = Path(value.strip())

    if not path.is_file():
        fail(f"ground truth not found: {path}")

    return path


def resolve_scorer_dir(ground_truth):
    value = os.getenv(SCORER_ENV)

    if value and value.strip():
        path = Path(value.strip())
    else:
        # <pkg>/data_v2/ground_truth.json -> <pkg>/server
        path = ground_truth.parent.parent / "server"

    if not (path / "scoring.py").is_file():
        fail(
            f"scoring.py not found in {path}. "
            f"Set {SCORER_ENV} to the folder containing it."
        )

    return path


def load_scoring(scorer_dir):
    sys.path.insert(0, str(scorer_dir))

    import scoring  # noqa: E402  (path must be set first)

    return scoring


def bar(value, width=22):
    filled = int(round(value * width))
    return "#" * filled + "-" * (width - filled)


def main(argv):
    import json

    submission_path = (
        Path(argv[0]).resolve() if argv else REPO_ROOT / "submission.json"
    )

    if not submission_path.is_file():
        fail(f"submission not found: {submission_path}")

    ground_truth = resolve_ground_truth()
    scoring = load_scoring(resolve_scorer_dir(ground_truth))

    truth = json.loads(ground_truth.read_text(encoding="utf-8"))
    submission = json.loads(submission_path.read_text(encoding="utf-8"))

    report = scoring.score_all(truth, submission)

    s1 = report["stage1"]
    s3 = report["stage3"]
    rel = report["reliability"]
    e2e = report["end_to_end"]
    categories = scoring.CATEGORIES

    print("=" * 72)
    print(f"  ShipGuard score — {submission_path.name}")
    print(f"  {report['n_emails']} emails")
    print("=" * 72)

    print(f"\nFINAL SCORE  {report['final_score']:.4f}")
    w = report["weights"]
    print(
        f"  weights: stage1={w['stage1']} stage3={w['stage3']} "
        f"end_to_end={w['end_to_end']}"
    )

    print("\nSTAGE 1 · classification")
    print(f"  accuracy  {s1['accuracy']:.3f}  {bar(s1['accuracy'])}")
    print(f"  macro-F1  {s1['macro_f1']:.3f}  {bar(s1['macro_f1'])}")

    print("\n  per-category   P / R / F1      (tp/fp/fn)")
    for category in categories:
        counts = s1["per"][category]
        p, r, f = scoring.prf(**counts)
        print(
            f"    {category:<15} {p:.2f} / {r:.2f} / {f:.2f}"
            f"   ({counts['tp']}/{counts['fp']}/{counts['fn']})"
        )

    print("\n  confusion (rows = gold, cols = predicted)")
    header = " " * 18 + "".join(c[:9].rjust(11) for c in categories) + "     total"
    print(header)

    predicted_totals = {c: 0 for c in categories}

    for gold in categories:
        row = s1["confusion"].get(gold, {})
        cells = ""
        for predicted in categories:
            n = row.get(predicted, 0)
            predicted_totals[predicted] += n
            cells += (str(n) if n else ".").rjust(11)
        print("    " + gold.ljust(14) + cells + str(sum(row.values())).rjust(10))

    print(
        "    " + "pred total".ljust(14)
        + "".join(str(predicted_totals[c]).rjust(11) for c in categories)
    )

    print("\nSTAGE 3 · SI vs BL comparison")
    print(f"  defect recall     {s3['defect_recall']:.3f}  {bar(s3['defect_recall'])}")
    print(
        f"  defect precision  {s3['defect_precision']:.3f}  "
        f"{bar(s3['defect_precision'])}"
    )
    print(f"  defect F1         {s3['defect_f1']:.3f}")
    print(f"  field-level F1    {s3['field_f1']:.3f}")
    print(f"  exact-match rate  {s3['exact_match_rate']:.3f}")
    print(f"  comparable docs   {s3['doc_total']}")

    print("\nRELIABILITY · escalate what you cannot decide (diagnostic)")
    print(
        f"  escalation recall     {rel['escalation_recall']:.3f}  "
        f"{bar(rel['escalation_recall'])}"
    )
    print(
        f"  escalation precision  {rel['escalation_precision']:.3f}  "
        f"{bar(rel['escalation_precision'])}"
    )
    print(f"  escalation F1         {rel['escalation_f1']:.3f}")
    print(f"  gold NEEDS_REVIEW {rel['gold_review']}   flagged {rel['pred_review']}")
    for reason, data in rel["per_reason"].items():
        print(f"    {reason:<20} {data['caught']}/{data['total']} escalated")

    print("\nEND-TO-END · headline metric")
    print(f"  {e2e['success']}/{e2e['total']} defect emails caught end to end")
    print(f"  rate  {e2e['rate']:.3f}  {bar(e2e['rate'])}")

    print("\n" + "-" * 72)
    print("  REGRESSION GATE")
    gate_ok = True

    if s3["defect_f1"] < 1.0:
        gate_ok = False
        print(f"  FAIL  stage3 defect F1 dropped to {s3['defect_f1']:.3f}")

    if e2e["rate"] < 1.0:
        gate_ok = False
        print(
            f"  FAIL  end-to-end dropped to {e2e['success']}/{e2e['total']}"
        )

    if gate_ok:
        print("  PASS  stage3 defect F1 = 1.000 and end-to-end = 100%")

    print("-" * 72)

    return 0 if gate_ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
