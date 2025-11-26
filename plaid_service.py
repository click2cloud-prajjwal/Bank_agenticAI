# backend/plaid_service.py
import os
from dotenv import load_dotenv
from plaid import Configuration, ApiClient
from plaid.api import plaid_api

load_dotenv()

def get_plaid_client():
    """
    Returns a PlaidApi client configured for the sandbox (uses PLAID_* env vars).
    """
    client_id = os.getenv("PLAID_CLIENT_ID")
    secret = os.getenv("PLAID_SECRET")
    env = os.getenv("PLAID_ENV", "sandbox").lower()

    if env == "sandbox":
        host = "https://sandbox.plaid.com"
    elif env == "development":
        host = "https://development.plaid.com"
    else:
        host = "https://production.plaid.com"

    configuration = Configuration(
        host=host,
        api_key={
            "clientId": client_id,
            "secret": secret,
        }
    )
    api_client = ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)
