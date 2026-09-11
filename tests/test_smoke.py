"""Дымовой тест: pytest вообще работает и находит тесты."""


def test_pytest_runs():
    assert True


def test_package_imports():
    import rusterm
    assert rusterm.__version__ == "0.1.0"


def test_subpackages_importable():
    import rusterm.store
    import rusterm.normalize
    import rusterm.core
    import rusterm.providers
    import rusterm.cli
