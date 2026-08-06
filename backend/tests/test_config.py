from backend.app.core.config import Settings


def test_allowed_origins_defaults_to_wildcard_when_unset():
    settings = Settings(_env_file=None)
    assert settings.allowed_origins_list() == ["*"]


def test_allowed_origins_splits_comma_separated_env_value():
    settings = Settings(_env_file=None, allowed_origins="https://a.example,https://b.example")
    assert settings.allowed_origins_list() == ["https://a.example", "https://b.example"]


def test_allowed_origins_strips_whitespace_around_commas():
    settings = Settings(_env_file=None, allowed_origins=" https://a.example , https://b.example ")
    assert settings.allowed_origins_list() == ["https://a.example", "https://b.example"]


def test_allowed_origins_single_value_with_no_comma():
    settings = Settings(_env_file=None, allowed_origins="https://only.example")
    assert settings.allowed_origins_list() == ["https://only.example"]


def test_allowed_origins_blank_env_value_falls_back_to_wildcard():
    # An operator setting ALLOWED_ORIGINS="" should not silently produce [""]
    # (a CORS origin that matches nothing) -- that would look configured but
    # actually block every browser request.
    settings = Settings(_env_file=None, allowed_origins="")
    assert settings.allowed_origins_list() == ["*"]
