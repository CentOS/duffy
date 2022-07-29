from unittest import mock

from duffy.app.database import req_db_async_session


@mock.patch("duffy.app.database.async_session_maker")
async def test_req_db_async_session(async_session_maker):
    mock_session = mock.AsyncMock()
    async_session_maker.return_value = mock_session

    n_iter = 0
    async for db_async_session in req_db_async_session():
        n_iter += 1
        assert db_async_session is mock_session
    mock_session.close.assert_awaited_with()
    assert n_iter == 1
