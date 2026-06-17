from app.config import get_timeout


def test_get_timeout_default():
    assert get_timeout({}) == 30
