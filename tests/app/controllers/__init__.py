import re

import pytest
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

from duffy.database.setup import _gen_test_api_key


@pytest.mark.usefixtures(
    "db_sync_schema",
    "db_sync_model_initialized",
    "db_async_schema",
    "db_async_model_initialized",
)
@pytest.mark.client_auth_as("admin")
class BaseTestController:
    """A class testing controllers.

    Attributes:
        name:   The name of the endpoint object to be tested.
        path:   The path to the endpoint in the API.
        attrs:  A dictionary of attributes needed to create an object in
                the API. Values can be tuples of other controller test
                classes and an item name to create such objects and use
                the respective items in the result.
        no_verify_attrs:
                A sequence of attribute names which should not be
                checked, e.g. because they are not returned in a
                response from the API endpoint or are expected to
                differ.
        unique: Whether or not objects with the same attributes can
                exist more than once. If it is a string, check whether
                it is in the error detail (case-insensitively). If it is
                a regular expression pattern object, check if it can
                matched anywhere in the error detail string.
        create_unprivileged:
                Whether or not non-admin users are allowed to create
                objects.

    Example:
        class TestFooController(BaseTestController):
            name = "foo"
            path = "/api/v1/foo"

        class TestBarController(BaseTestController):
            name = "bar"
            path = "/api/v1/bar"
            attrs = {"foo_id": (TestFooController, "id")}

            ...

            async def test_method(client):
                response = await self._create_obj(client)
                result = response.json()
                bar1 = result["bar"]

                ...

                response = await self._create_obj(
                    client, attrs={"foo_id": bar1["id"]}
                )
                result = response.json()
                bar2 = result["bar"]

                ...

                response = await self._create_obj(
                    client, attrs={"new_attrs": {...}}, merge_cls_attrs=False
                )
                result = response.json()
                bar3 = result["bar"]

                ...
    """

    name = None
    path = None
    attrs = {}
    no_verify_attrs = ()
    unique = False
    create_unprivileged = False

    @property
    def name_plural(self):
        """This is used for returning collections of objects from the API."""
        return self.name + "s"

    @classmethod
    async def _create_obj(
        cls,
        client,
        attrs: dict = None,
        merge_cls_attrs: bool = True,
        client_kwargs: dict = None,
        subcls_client_kwargs: dict = None,
    ):
        if merge_cls_attrs:
            attrs = {**(cls.attrs or {}), **(attrs or {})}
        else:
            attrs = attrs or {}

        if client_kwargs is None:
            client_kwargs = {}

        if subcls_client_kwargs is None:
            subcls_client_kwargs = client_kwargs
        else:
            subcls_client_kwargs = {**client_kwargs, **subcls_client_kwargs}

        for name, value in attrs.items():
            try:
                subcls, item = value
            except (TypeError, ValueError):
                pass
            else:
                if isinstance(subcls, type) and issubclass(subcls, BaseTestController):
                    subresponse = await subcls._create_obj(
                        client, client_kwargs=subcls_client_kwargs
                    )
                    subresult = subresponse.json()
                    value = subresult[subcls.name]
                    for elem in item.split("."):
                        value = value[elem]
                attrs[name] = value

        response = await client.post(cls.path, json=attrs, **client_kwargs)
        return response

    @classmethod
    def _verify_item(cls, item, attrs=None, no_verify_attrs=None):
        if not attrs:
            attrs = cls.attrs
        if not no_verify_attrs:
            no_verify_attrs = cls.no_verify_attrs
        for key, value in attrs.items():
            if key in no_verify_attrs:
                continue
            try:
                subcls, _ = cls.attrs[key]
            except (TypeError, ValueError):
                pass
            else:
                if isinstance(subcls, type) and issubclass(subcls, BaseTestController):
                    # skip verifying objects this one depends on
                    continue
            assert item[key] == value

    @pytest.mark.parametrize(
        "unprivileged",
        (
            False,
            pytest.param(True, marks=pytest.mark.client_auth_as("tenant")),
        ),
    )
    async def test_create_obj(self, unprivileged, client, auth_admin):
        """Test that objects can be created on the API endpoint."""
        # Ensure that dependencies are created as admin tenant.
        response = await self._create_obj(
            client,
            subcls_client_kwargs={
                "auth": (auth_admin.name, str(_gen_test_api_key(auth_admin.name)))
            },
        )
        if not unprivileged or self.create_unprivileged:
            assert response.status_code == HTTP_201_CREATED
            result = response.json()
            self._verify_item(result[self.name])
        else:
            assert response.status_code == HTTP_403_FORBIDDEN

    @classmethod
    def _add_attrs_from_response(cls, response):
        result = response.json()
        obj = result[cls.name]

        retval = {}
        for name, value in cls.attrs.items():
            if name in cls.no_verify_attrs:
                continue
            try:
                subcls, item = value
            except (TypeError, ValueError):
                pass
            else:
                if isinstance(subcls, type) and issubclass(subcls, BaseTestController):
                    value = obj
                    for elem in item.split("."):
                        value = value[elem]

            retval[name] = value

        return retval

    async def test_create_duplicate_obj(self, client):
        """Test that adding an object twice works or will violate a constraint.

        This depends on how the `unique` attribute is set.
        """
        create_response = await self._create_obj(client)

        response = await self._create_obj(
            client, attrs=self._add_attrs_from_response(create_response)
        )
        if self.unique:
            assert response.status_code == HTTP_409_CONFLICT
            result = response.json()
            if isinstance(self.unique, str):
                assert self.unique in result["detail"].lower()
            elif isinstance(self.unique, re.Pattern):
                assert self.unique.search(result["detail"])
        else:
            assert response.status_code == HTTP_201_CREATED

    @pytest.mark.parametrize("testcase", ("found", "not found"))
    async def test_retrieve_obj(self, client, testcase):
        """Test that an object can be retrieved via the API endpoint."""
        if testcase != "not found":
            create_response = await self._create_obj(client)
            obj_id = create_response.json()[self.name]["id"]
        else:
            obj_id = -1

        response = await client.get(f"{self.path}/{obj_id}")

        if testcase == "found":
            assert response.status_code == HTTP_200_OK
            result = response.json()
            attrs = {**self.attrs, **self._add_attrs_from_response(create_response)}
            self._verify_item(result[self.name], attrs=attrs)
        else:
            assert response.status_code == HTTP_404_NOT_FOUND

    async def test_retrieve_collection(self, client):
        """Test that a collection of objects can be retrieved from the API endpoint."""
        create_response = await self._create_obj(client)

        response = await client.get(self.path)
        result = response.json()
        assert self.name_plural in result
        objs = result[self.name_plural]
        obj = objs[-1]
        assert obj["id"] == len(objs)
        attrs = {**self.attrs, **self._add_attrs_from_response(create_response)}
        self._verify_item(obj, attrs=attrs)
