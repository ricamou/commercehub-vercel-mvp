from app.services.token_service import TokenService


def test_token_service_returns_storage_mode():
    result = TokenService().get_token_status()
    assert result["storage_mode"] == "environment_variables"
