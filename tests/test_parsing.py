from agent_sandbox.parsing.regex_parser import parse_with_regex
from agent_sandbox.parsing.schemas import ParsedError


def test_parse_with_regex_returns_structured_error():
    log = """Traceback (most recent call last):
  File "app/service.py", line 18, in calculate_total
    return price + tax
TypeError: unsupported operand type(s) for +: 'int' and 'str'
"""

    parsed = parse_with_regex(log)

    assert isinstance(parsed, ParsedError)
    assert parsed.error_type == "TypeError"
    assert parsed.file_path == "app/service.py"
    assert parsed.line_number == 18
    assert parsed.function_name == "calculate_total"
