import os
from dotenv import load_dotenv
from openai import OpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

def main():
    # Load environment variables from the local .env file
    load_dotenv()

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment_name = os.getenv("AZURE_DEPLOYMENT_NAME")

    if not endpoint or not deployment_name:
        print("[-] Error: Missing required environment variables in .env file.")
        return

    print(f"[+] Initializing Azure OpenAI client for deployment: {deployment_name}")

    try:
        # Fetch a dynamic token provider for Azure AI Foundry.
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), 
            "https://ai.azure.com/.default"
        )

        # Azure AI Foundry exposes an OpenAI-compatible /openai/v1 endpoint.
        client = OpenAI(
            base_url=endpoint,
            api_key=token_provider,
        )

        # Execute a simple chat completion to verify network connectivity and permissions
        completion = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {
                    "role": "user",
                    "content": "Ping"
                }
            ],
        )

        print("🚀 [Success] Azure Entra ID authentication token verified!")
        print(f"[*] Response from model: {completion.choices[0].message.content}")

    except Exception as e:
        print("❌ [Failure] Day 0 smoke test failed.")
        print(f"[-] Technical details: {str(e)}")

if __name__ == "__main__":
    main()
