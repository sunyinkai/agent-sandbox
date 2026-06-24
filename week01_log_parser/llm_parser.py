import os
from typing import Optional
from week01_log_parser.openai_helper import get_client
from week01_log_parser.schemas import ParsedError

SYSTEM_PROMPT = """
You are a Python error log parser.

Extract structured information from messy Python tracebacks, pytest failures, and natural language bug reports.

Rules:
- Extract the final Python exception type as error_type when possible.
- raw_message should contain the core exception message, without unnecessary log noise.
- file_path should point to the most relevant user-code file, not third-party library files when avoidable.
- line_number should be the most relevant failing line if available.
- function_name should be the most relevant function or test name if available.
- If a field is unknown, use null.
- Do not invent file paths, line numbers, or function names. They could be null
- severity must be one of: low, medium, high.
"""


def parse_with_llm(log: str) -> Optional[ParsedError]:
    client = get_client()
    if client is None:
        print("[-] Error: Failed to create client")
        return None
    try:
        response = client.responses.parse(
            model=os.getenv("AZURE_DEPLOYMENT_NAME"),
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": log},
            ],
            text_format=ParsedError,
        )

        return response.output_parsed
    except Exception as e:
        print("[-] Error: LLM parsing failed:", e)
        return None


if __name__ == "__main__":
    log = 'Traceback (most recent call last):\n  File "scripts/migrate.py", line 81, in <module>\n    migrate()\n  File "scripts/migrate.py", line 44, in migrate\n    version = int(record["version"])\nValueError: invalid literal for int() with base 10: \'v2\''
    print(parse_with_llm(log))
