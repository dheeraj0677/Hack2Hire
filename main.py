"""
Interview Simulation Engine — CLI Entry Point.

Usage:
    python main.py --input samples/sample_input.json
    python main.py --input samples/sample_input.json --output result.json
    python main.py --input samples/sample_input.json --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine.state_machine import InterviewEngine


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Interview Simulation Engine — Processes a structured interview "
        "log and produces a final Interview Readiness Score.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py --input samples/sample_input.json\n"
            "  python main.py --input samples/sample_input.json --output result.json\n"
            "  python main.py --input samples/sample_input.json --verbose\n"
        ),
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the JSON input file containing the interview log.",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Path to write the JSON output. If omitted, prints to stdout.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose step-by-step trace output.",
    )

    args = parser.parse_args()

    # ── Load Input ──────────────────────────────
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {input_path}: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error reading {input_path}: {e}", file=sys.stderr)
        return 1

    # ── Run Engine ──────────────────────────────
    engine = InterviewEngine(verbose=args.verbose)
    output = engine.run(raw_data)

    # ── Write Output ────────────────────────────
    result_json = json.dumps(output.to_dict(), indent=2, ensure_ascii=False)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result_json)
        print(f"✓ Output written to {output_path}")
    else:
        print(result_json)

    # ── Summary ─────────────────────────────────
    print("\n" + "=" * 60, file=sys.stderr)
    print(f"  Interview Readiness Score: {output.interview_readiness_score:.1f}/100", file=sys.stderr)
    print(f"  Status: {output.status}", file=sys.stderr)
    print(f"  Questions: {output.questions_answered}/{output.questions_attempted} answered", file=sys.stderr)
    print(f"  Time: {output.total_time_seconds:.0f}s", file=sys.stderr)
    print(f"  Skill Match: {output.skill_match_score:.0%}", file=sys.stderr)
    if output.category_breakdown:
        print("  Category Scores:", file=sys.stderr)
        for cat in output.category_breakdown:
            print(f"    {cat.category}: {cat.percentage:.1f}%", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
