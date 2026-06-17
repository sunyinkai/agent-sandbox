from app.cart import calculate_total


def test_calculate_total_with_string_price():
    items = [
        {"price": "10"},
        {"price": "5"},
    ]
    assert calculate_total(items) == 15
