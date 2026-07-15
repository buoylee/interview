from order_service import __version__


def test_package_has_pinned_tutorial_version() -> None:
    assert __version__ == "0.1.0"
