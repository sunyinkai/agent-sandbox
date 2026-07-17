from agent_sandbox.repair.test_runner import parse_pytest_errors


def test_parse_pytest_errors_returns_failure_details():
    report = {
        "tests": [
            {
                "nodeid": "tests/test_cart.py::test_total",
                "outcome": "failed",
                "call": {
                    "crash": {
                        "message": "AssertionError: assert 10 == 15",
                        "path": "tests/test_cart.py",
                        "lineno": 12,
                    },
                    "longrepr": "assert 10 == 15",
                },
            }
        ]
    }

    errors = parse_pytest_errors(report)

    assert len(errors) == 1
    assert errors[0].test_name == "tests/test_cart.py::test_total"
    assert errors[0].error_type == "AssertionError"
    assert errors[0].file_path == "tests/test_cart.py"
    assert errors[0].line_number == 12
