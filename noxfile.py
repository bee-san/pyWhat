"""Nox sessions."""
from typing import Any

import nox
from nox.sessions import Session

nox.options.sessions = ["tests"]
locations = "src", "tests", "noxfile.py", "docs/conf.py"


def install_with_constraints(session: Session, *args: str, **kwargs: Any) -> None:
    """Install packages constrained by Poetry's lock file.
    This function is a wrapper for nox.sessions.Session.install. It
    invokes pip to install packages inside of the session's virtualenv.
    Additionally, pip is passed a constraints file generated from
    Poetry's lock file, to ensure that the packages are pinned to the
    versions specified in poetry.lock. This allows you to manage the
    packages as Poetry development dependencies.
    Arguments:
        session: The Session object.
        args: Command-line arguments for pip.
        kwargs: Additional keyword arguments for Session.install.
    """
    session.run(
        "poetry",
        "export",
        "--without-hashes",
        "--dev",
        "--format=requirements.txt",
        "--output=requirements.txt",
        external=True,
    )
    session.install("--constraint=requirements.txt", *args, **kwargs)


@nox.session
def tests(session: Session) -> None:
    """Run the test suite."""
    session.run("poetry", "install", "--no-dev", external=True)
    install_with_constraints(
        session, "pytest", "pytest-black", "pytest-isort", "pytest-mypy"
    )
    session.run("pytest")
