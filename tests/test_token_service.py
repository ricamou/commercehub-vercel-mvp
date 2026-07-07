from app.services.token_service import TokenService


def test_token_service_returns_storage_mode():
    service = TokenService()
    result = service.get_token_status()

    assert result["storage_mode"] == "environment_variables"
