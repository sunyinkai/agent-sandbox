from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI
from azure.identity import (
    AzureCliCredential,
    DefaultAzureCredential,
    get_bearer_token_provider,
)
import os

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
