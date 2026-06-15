import argparse
import json
from pathlib import Path

from pipeline import parsed_error_log


def load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def field_match(parsed_value, expected_value):
    if expected_value is None:
        return parsed_value is None
    return parsed_value == expected_value


def evaluate(file_path: Path):
    total = 0
    parsed_success = 0

    field_stats = {
        "error_type": {"correct": 0, "total": 0},
        "file_path": {"correct": 0, "total": 0},
        "line_number": {"correct": 0, "total": 0},
        "function_name": {"correct": 0, "total": 0},
        "raw_message_contains": {"correct": 0, "total": 0},
    }

    failures = []

    for item in load_jsonl(file_path):
        total += 1
        parsed = parsed_error_log(item["log"])
        expected = item.get("expected", {})

        if parsed is None:
            failures.append(
                {
                    "id": item.get("id"),
                    "reason": "parse_failed",
                    "expected": expected,
                    "parsed": None,
                }
            )
            continue

        parsed_success += 1
        parsed_dict = parsed.model_dump()

        for field in ["error_type", "file_path", "line_number", "function_name"]:
            if field in expected:
                field_stats[field]["total"] += 1
                if field_match(parsed_dict.get(field), expected[field]):
                    field_stats[field]["correct"] += 1
                else:
                    failures.append(
                        {
                            "id": item.get("id"),
                            "reason": f"{field}_mismatch",
                            "expected": expected.get(field),
                            "parsed": parsed_dict.get(field),
                        }
                    )

        if "raw_message_contains" in expected:
            field_stats["raw_message_contains"]["total"] += 1
            expected_substring = expected["raw_message_contains"]
            raw_message = parsed.raw_message or ""

            if expected_substring in raw_message:
                field_stats["raw_message_contains"]["correct"] += 1
            else:
                failures.append(
                    {
                        "id": item.get("id"),
                        "reason": "raw_message_mismatch",
                        "expected_contains": expected_substring,
                        "parsed": raw_message,
                    }
                )

    print(f"Parsed success: {parsed_success}/{total} = {parsed_success / total:.2%}")

    print("\nField accuracy:")
    for field, stat in field_stats.items():
        if stat["total"] == 0:
            continue
        print(
            f"- {field}: {stat['correct']}/{stat['total']} = {stat['correct'] / stat['total']:.2%}"
        )

    print("\nFailures:")
    for failure in failures[:20]:
        print(json.dumps(failure, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Evaluate parsed_error_log accuracy on a JSONL log dataset."
    )
    parser.add_argument(
        "--file_path",
        type=Path,
        required=True,
        help="Path to the JSONL dataset to evaluate.",
    )
    args = parser.parse_args()

    evaluate(args.file_path)
