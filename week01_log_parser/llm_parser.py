import os
from dotenv import load_dotenv
from openai import OpenAI
from azure.identity import (
    AzureCliCredential,
    DefaultAzureCredential,
    get_bearer_token_provider,
)
from typing import Optional

try:
    from .schemas import ParsedError
except ImportError:
    from schemas import ParsedError

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

_client: Optional[OpenAI] = None


def get_client() -> Optional[OpenAI]:
    global _client
    if _client is not None:
        return _client

    load_dotenv()
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment_name = os.getenv("AZURE_DEPLOYMENT_NAME")
    tenant_id = os.getenv("AZURE_TENANT_ID")

    if not endpoint or not deployment_name:
        print("[-] Error: Missing required environment variables in .env file.")
        return None

    try:
        if tenant_id:
            credential = AzureCliCredential(
                tenant_id=tenant_id,
                additionally_allowed_tenants=["*"],
            )
        else:
            credential = DefaultAzureCredential(additionally_allowed_tenants=["*"])

        # Fetch a dynamic token provider for Azure AI Foundry.
        token_provider = get_bearer_token_provider(
            credential, "https://ai.azure.com/.default"
        )

        # Azure AI Foundry exposes an OpenAI-compatible /openai/v1 endpoint.
        _client = OpenAI(
            base_url=endpoint,
            api_key=token_provider,
        )
        return _client
    except Exception as e:
        print("[-] Error: Failed to create client", e)
        return None


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
