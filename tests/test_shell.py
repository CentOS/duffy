from unittest import mock

import pytest

from duffy import database, exceptions, shell
from duffy.database import model

from .util import noop_context


@pytest.mark.parametrize("with_ipython", (True, False))
@mock.patch("duffy.shell.IPython", new=mock.MagicMock())
def test_get_available_shells(with_ipython):
    if not with_ipython:
        shell.IPython = None

    shells = shell.get_available_shells()

    assert "python" in shells
    if with_ipython:
        assert "ipython" in shells
    else:
        assert "ipython" not in shells


@pytest.mark.parametrize(
    "with_ipython, with_autoawait", ((False, False), (True, False), (True, True))
)
@mock.patch("duffy.shell.IPython")
def test_get_shell_variables(IPython, with_ipython, with_autoawait):
    if not with_autoawait:
        IPython.InteractiveShell.autoawait = False

    variables = shell.get_shell_variables("ipython" if with_ipython else "python")

    assert variables["SyncDBSession"] is database.SyncDBSession
    # Do a spot check of one model class.
    assert variables["User"] is model.User

    if with_ipython and with_autoawait:
        assert variables["DBSession"] is database.DBSession
    else:
        # The asynchronous DBSession must only be made available if the shell does its part.
        assert "DBSession" not in variables


@mock.patch("duffy.shell.code")
@mock.patch("duffy.shell.get_shell_variables")
def test_embed_python_shell(get_shell_variables, code):
    sentinel = object()
    get_shell_variables.return_value = sentinel

    shell_obj = mock.MagicMock()
    code.InteractiveConsole.return_value = shell_obj

    shell.embed_python_shell()

    get_shell_variables.assert_called_once_with(shell_type="python")
    code.InteractiveConsole.assert_called_once_with(sentinel)

    shell_obj.interact.assert_called_once_with()


@pytest.mark.parametrize(
    "with_autoawait, get_event_loop_errors", ((True, False), (True, True), (False, False))
)
@mock.patch("duffy.shell.get_shell_variables")
@mock.patch("duffy.shell.asyncio")
@mock.patch("duffy.shell.IPython")
def test_embed_ipython_shell(
    IPython, asyncio, get_shell_variables, with_autoawait, get_event_loop_errors
):
    sentinel = object()
    get_shell_variables.return_value = sentinel

    if with_autoawait:
        IPython.InteractiveShell.autoawait = True
        if get_event_loop_errors:
            asyncio.get_event_loop.side_effect = RuntimeError(
                "There is no current event loop in thread 'MainThread'."
            )
    else:
        IPython.InteractiveShell.autoawait = False

    shell.embed_ipython_shell()

    if with_autoawait:
        asyncio.get_event_loop.assert_called_once_with()

    get_shell_variables.assert_called_once_with(shell_type="ipython")
    IPython.start_ipython.assert_called_once_with(argv=[], user_ns=sentinel)


@pytest.mark.parametrize("shell_type", (None, "python", "ipython"))
@mock.patch("duffy.shell.embed_ipython_shell")
@mock.patch("duffy.shell.embed_python_shell")
@mock.patch("duffy.shell.get_available_shells")
def test_embed_shell(get_available_shells, embed_python_shell, embed_ipython_shell, shell_type):
    if shell_type is None:
        get_available_shells.return_value = ["default"]
        expectation = pytest.raises(exceptions.DuffyShellUnavailableError, match="default")
    else:
        expectation = noop_context()

    with expectation:
        shell.embed_shell(shell_type=shell_type)

    if shell_type is None:
        get_available_shells.assert_called_once_with()
    else:
        get_available_shells.assert_not_called()
        if shell_type == "python":
            embed_python_shell.assert_called_once_with()
            embed_ipython_shell.assert_not_called()
        elif shell_type == "ipython":
            embed_ipython_shell.assert_called_once_with()
            embed_python_shell.assert_not_called()
