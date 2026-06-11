import os
from dotenv import load_dotenv
from openai import OpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from schemas import ParsedError
from typing import Optional

_client: Optional[OpenAI] = None

def get_client() -> Optional[OpenAI]:
    global _client
    if _client is not None:
        return _client

    load_dotenv()
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment_name = os.getenv("AZURE_DEPLOYMENT_NAME")

    if not endpoint or not deployment_name:
        print("[-] Error: Missing required environment variables in .env file.")
        return

    try:
        # Fetch a dynamic token provider for Azure AI Foundry.
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), 
            "https://ai.azure.com/.default"
        )

        # Azure AI Foundry exposes an OpenAI-compatible /openai/v1 endpoint.
        _client = OpenAI(
            base_url=endpoint,
            api_key=token_provider,
        )
        return _client
    except Exception as e:
        print("[-] Error: Failed to create client",e)
        return None
    
def parse_with_llm(log: str) -> Optional[ParsedError]:
    client = get_client()
    if client is None:
        print("[-] Error: Failed to create client")
        return None
    response = client.responses.parse(
        model =  os.getenv("AZURE_DEPLOYMENT_NAME"),
        input=[{
            "role":"system",
            "content":"you are a python error parser, you need to extract the required information correctly for customer locating the issue"
        },{
            "role":"user",
            "content":log
        }],
        text_format=ParsedError
    )

    for output in response.output:
        if output.type != "message":
            continue
        for item in output.content:
            if item.type == "refusal":
                # If the model refuses to respond, you will get a refusal message
                print(item.refusal)
                continue

            if not item.parsed:
                raise Exception("Could not parse response")
            else:
               return item.parsed

if __name__ == "__main__":
    log="Traceback (most recent call last):\n  File \"scripts/migrate.py\", line 81, in <module>\n    migrate()\n  File \"scripts/migrate.py\", line 44, in migrate\n    version = int(record[\"version\"])\nValueError: invalid literal for int() with base 10: 'v2'"
    parse_with_llm(log)