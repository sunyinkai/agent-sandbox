from app.users import get_user_name


def test_get_user_name_with_none():
    assert get_user_name(None) == "UNKNOWN"
