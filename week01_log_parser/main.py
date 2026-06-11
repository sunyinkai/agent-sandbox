import argparse
import json

from regex_parser import parse_with_regex


def load_jsonl(path: str):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    total = 0
    success = 0

    for item in load_jsonl(args.input):
        total += 1
        parsed = parse_with_regex(item["log"])

        if parsed:
            success += 1
            print(json.dumps(parsed.model_dump(), ensure_ascii=False))
        else:
            print(json.dumps({"id": item["id"], "error": "parse_failed"}, ensure_ascii=False))

    print(f"\nSuccess rate: {success}/{total} = {success / total:.2%}")


if __name__ == "__main__":
    main()