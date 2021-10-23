import logging


def pytest_configure(config):
    # Silence Flake8 warnings
    logging.getLogger("flake8").setLevel(logging.ERROR)
