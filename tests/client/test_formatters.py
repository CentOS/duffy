import datetime as dt
import json
from contextlib import nullcontext

import pytest

from duffy.api_models import (
    PoolConciseModel,
    PoolLevelsModel,
    PoolResult,
    PoolResultCollection,
    PoolVerboseModel,
    SessionModel,
    SessionNodeModel,
    SessionResult,
    SessionResultCollection,
    TenantModel,
)
from duffy.client.formatter import (
    DuffyFlatFormatter,
    DuffyFormatter,
    DuffyJSONFormatter,
    DuffyYAMLFormatter,
)
from duffy.client.main import DuffyAPIErrorModel

TEST_JSON_DICT = {"test_key": "test_value"}


class TestDuffyFormatter:
    @pytest.mark.parametrize(
        "format, formatter_cls",
        (
            ("json", DuffyJSONFormatter),
            ("yaml", DuffyYAMLFormatter),
            ("flat", DuffyFlatFormatter),
        ),
    )
    def test_new_for_format(self, format, formatter_cls):
        fmtobj = DuffyFormatter.new_for_format(format)
        assert isinstance(fmtobj, formatter_cls)

    def test_format(self):
        with pytest.raises(NotImplementedError):
            DuffyFormatter().format(TEST_JSON_DICT)


class TestDuffyJSONFormatter:
    def test_format(self):
        formatted = DuffyJSONFormatter().format(TEST_JSON_DICT)
        assert json.loads(formatted) == TEST_JSON_DICT


class TestDuffyYAMLFormatter:
    def test_format(self):
        formatted = DuffyYAMLFormatter().format(TEST_JSON_DICT)
        assert formatted == "test_key: test_value\n"


class TestDuffyFlatFormatter:
    CREATED_AT = dt.datetime(year=2022, month=5, day=31, hour=12, minute=0, second=0)
    TEST_SESSION = SessionModel(
        id=17,
        active=True,
        created_at=CREATED_AT,
        retired_at=None,
        tenant=TenantModel(
            id=1,
            active=True,
            created_at=CREATED_AT,
            name="tenant",
            ssh_key="foo",
            effective_node_quota=10,
            effective_session_lifetime=dt.timedelta(hours=6),
            effective_session_lifetime_max=dt.timedelta(hours=12),
        ),
        data={},
        nodes=[
            SessionNodeModel(
                id=32,
                hostname="hostname",
                ipaddr="127.0.0.1",
                pool="pool",
                reusable=True,
                data={},
            ),
        ],
    )
    TEST_POOL_CONCISE = PoolConciseModel(name="pool", **{"fill-level": 15})
    TEST_POOL_VERBOSE = PoolVerboseModel(
        name="pool",
        levels=PoolLevelsModel(
            provisioning=0, ready=15, contextualizing=0, deployed=5, deprovisioning=0
        ),
        **{"fill-level": 15},
    )

    @pytest.mark.parametrize(
        "value, expected",
        (
            (None, ""),
            (True, "TRUE"),
            (False, "FALSE"),
            (5, 5),
            (5.5, 5.5),
            ("abc", "'abc'"),
            ("ab'cd", "'ab'\"'\"'cd'"),
        ),
    )
    def test_format_key_value(self, value, expected):
        assert DuffyFlatFormatter.format_key_value("boo", value) == f"boo={expected}"

    def test_flatten_api_error(self):
        api_error = DuffyAPIErrorModel(error={"detail": "Hullo."})
        node_line = next(DuffyFlatFormatter().flatten_api_error(api_error=api_error))
        assert node_line == "error='Hullo.'"

    def test_flatten_pool(self):
        pool_line = next(
            DuffyFlatFormatter().flatten_pool(pool=self.TEST_POOL_VERBOSE.model_dump(by_alias=True))
        )

        assert pool_line == (
            "pool_name='pool' fill_level=15 levels_provisioning=0 levels_ready=15"
            " levels_contextualizing=0 levels_deployed=5 levels_deprovisioning=0"
        )

    def test_flatten_pool_result(self):
        pool_line = next(
            DuffyFlatFormatter().flatten_pool_result(
                PoolResult(action="get", pool=self.TEST_POOL_VERBOSE).model_dump(by_alias=True)
            )
        )

        assert pool_line == (
            "pool_name='pool' fill_level=15 levels_provisioning=0 levels_ready=15"
            " levels_contextualizing=0 levels_deployed=5 levels_deprovisioning=0"
        )

    def test_flatten_pools_result(self):
        pool_line = next(
            DuffyFlatFormatter().flatten_pools_result(
                PoolResultCollection(action="get", pools=[self.TEST_POOL_CONCISE]).model_dump(
                    by_alias=True
                )
            )
        )

        assert pool_line == "pool_name='pool' fill_level=15"

    def test_flatten_session(self):
        node_line = next(
            DuffyFlatFormatter().flatten_session(
                session=self.TEST_SESSION.model_dump(by_alias=True)
            )
        )

        assert node_line == (
            "session_id=17 active=TRUE created_at='2022-05-31 12:00:00' retired_at= pool='pool'"
            " hostname='hostname' ipaddr='127.0.0.1'"
        )

    def test_flatten_session_result(self):
        node_line = next(
            DuffyFlatFormatter().flatten_session_result(
                SessionResult(action="get", session=self.TEST_SESSION).model_dump(by_alias=True)
            )
        )

        assert node_line == (
            "session_id=17 active=TRUE created_at='2022-05-31 12:00:00' retired_at= pool='pool'"
            " hostname='hostname' ipaddr='127.0.0.1'"
        )

    def test_flatten_sessions_result(self):
        node_line = next(
            DuffyFlatFormatter().flatten_sessions_result(
                SessionResultCollection(action="get", sessions=[self.TEST_SESSION]).model_dump(
                    by_alias=True
                )
            )
        )

        assert node_line == (
            "session_id=17 active=TRUE created_at='2022-05-31 12:00:00' retired_at= pool='pool'"
            " hostname='hostname' ipaddr='127.0.0.1'"
        )

    @pytest.mark.parametrize(
        "result_cls",
        (PoolResult, PoolResultCollection, SessionResult, SessionResultCollection, dict),
    )
    def test_format(self, result_cls):
        expectation = nullcontext()
        api_result = None

        if result_cls == PoolResult:
            model_result = PoolResult(action="get", pool=self.TEST_POOL_VERBOSE)
        elif result_cls == PoolResultCollection:
            model_result = PoolResultCollection(action="get", pools=[self.TEST_POOL_CONCISE])
        elif result_cls == SessionResult:
            model_result = SessionResult(action="get", session=self.TEST_SESSION)
        elif result_cls == SessionResultCollection:
            model_result = SessionResultCollection(action="get", sessions=[self.TEST_SESSION])
        else:
            api_result = {"a dict": "contents don't matter"}
            expectation = pytest.raises(TypeError)

        if not api_result:
            api_result = model_result.model_dump(by_alias=True)

        with expectation:
            formatted = DuffyFlatFormatter().format(api_result)

        if result_cls is PoolResult:
            assert formatted == (
                "pool_name='pool' fill_level=15 levels_provisioning=0 levels_ready=15"
                " levels_contextualizing=0 levels_deployed=5 levels_deprovisioning=0"
            )
        elif result_cls is PoolResultCollection:
            assert formatted == "pool_name='pool' fill_level=15"
        elif result_cls in (SessionResult, SessionResultCollection):
            assert formatted == (
                "session_id=17 active=TRUE created_at='2022-05-31 12:00:00' retired_at= pool='pool'"
                " hostname='hostname' ipaddr='127.0.0.1'"
            )
