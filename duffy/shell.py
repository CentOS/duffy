import asyncio
import code
import readline  # noqa: F401
from typing import Optional

try:
    import IPython
except ImportError:  # pragma: no cover
    IPython = None

import sqlalchemy

from . import database
from .database import model
from .exceptions import DuffyShellUnavailableError


def get_available_shells():
    shells = ["python"]
    if IPython:
        shells.append("ipython")
    return shells


def get_shell_variables(shell_type: str):
    variables = {
        "SyncDBSession": database.SyncDBSession,
        "sqlalchemy": sqlalchemy,
        "select": sqlalchemy.select,
    }

    if shell_type == "ipython" and IPython.InteractiveShell.autoawait:
        # Since IPython 7.0, Python 3.6, you can `await` coroutines in the IPython REPL, so we
        # inject the asynchronous database session object into the namespace of the shell.
        variables["DBSession"] = database.DBSession

    # Insert all DB model classes into the local namespace.
    for objname in dir(model):
        obj = getattr(model, objname)
        if isinstance(obj, type) and obj.__module__ == "duffy.database.model":
            variables[objname] = obj

    return variables


def embed_python_shell():
    shell = code.InteractiveConsole(get_shell_variables(shell_type="python"))
    shell.interact()


def embed_ipython_shell():
    if IPython.InteractiveShell.autoawait:
        # Ensure a usable asyncio event loop exists to enable the autoawait functionality of
        # IPython.
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None
        if not loop:
            asyncio.set_event_loop(asyncio.new_event_loop())

    IPython.start_ipython(argv=[], user_ns=get_shell_variables(shell_type="ipython"))


def embed_shell(shell_type: Optional[str]):
    if shell_type is None:
        shell_type = get_available_shells()[-1]

    if shell_type == "ipython":
        embed_ipython_shell()
    elif shell_type == "python":
        embed_python_shell()
    else:
        raise DuffyShellUnavailableError(shell_type)
