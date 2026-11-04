"""Nox sessions."""
from os import environ

import nox
from nox.sessions import Session

nox.options.sessions = ["tests"]
if environ.get("CI", None) == "true":
    nox.options.sessions.append("coverage")


@nox.session
def tests(session: Session) -> None:
    """Run the test suite, on the Rust engine."""
    # The tools, at the versions in requirements-dev.txt (see requirements-dev.in)
    session.install("-r", "requirements-dev.txt")
    # Builds the extension module pywhat._pywhat with maturin, which needs a Rust
    # toolchain (cargo). pytest imports pywhat from the checkout, which comes first on
    # sys.path, so the install is editable: maturin puts the extension into pywhat/,
    # and the coverage is that of the files of the checkout.
    session.install("-e", ".")
    session.run("pytest", "--cov=./", "--cov-report=xml")


@nox.session
def coverage(session: Session) -> None:
    """Upload coverage data."""
    session.install("--constraint=requirements-dev.txt", "codecov")
    session.run("codecov", "--env", "OS", "PYTHON")
