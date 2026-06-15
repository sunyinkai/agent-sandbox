from typing import Optional, TypedDict

from regex_parser import parse_with_regex
from llm_parser import parse_with_llm
from schemas import ParsedError


def parsed_error_log(log: str) -> Optional[ParsedError]:
    parsed = parse_with_regex(log)
    if (
        parsed is None
        or parsed.file_path is None
        or parsed.line_number is None
        or parsed.function_name is None
    ):
        parsed = parse_with_llm(log)

    return parsed
