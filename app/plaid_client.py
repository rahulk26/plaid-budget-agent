from plaid.api import plaid_api
from plaid import Configuration, ApiClient, Environment
from .config import settings

def get_plaid_client() -> plaid_api.PlaidApi:
    env_map = {
        "sandbox": Environment.Sandbox,
        "development": Environment.Development,
        "production": Environment.Production,
    }
    configuration = Configuration(
        host=env_map.get(settings.plaid_env, Environment.Sandbox),
        api_key={
            "clientId": settings.plaid_client_id,
            "secret": settings.plaid_secret,
        }
    )
    api_client = ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)
