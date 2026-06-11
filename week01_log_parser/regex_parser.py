import re
from typing import Optional

from schemas import ParsedError


def parse_with_regex(log: str) -> Optional[ParsedError]:
    # Match exception line, for example:
    # TypeError: unsupported operand type(s) for +: 'int' and 'str'
    error_matches = re.findall(
        r"([A-Za-z_][A-Za-z0-9_]*Error|Exception):\s*([^\n]*)",
        log,
    )

    if not error_matches:
        return None

    error_type, raw_message = error_matches[-1]

    # Match file path, for example:
    # File "app/service.py", line 18, in calculate_total
    file_matches = re.findall(
        r'File "([^"]+)",',
        log,
    )
    file_path = file_matches[-1] if file_matches else None

    # Match line number
    line_matches = re.findall(
        r", line (\d+)",
        log,
    )
    line_number = int(line_matches[-1]) if line_matches else None

    # Match function name
    function_matches = re.findall(
        r'File "[^"]+", line \d+, in ([^\n]+)',
        log,
    )
    function_name = function_matches[-1].strip() if function_matches else None

    return ParsedError(
        error_type=error_type,
        file_path=file_path,
        line_number=line_number,
        function_name=function_name,
        raw_message=raw_message,
        likely_cause=None,
        severity="low",
    )