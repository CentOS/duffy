import re

import pytest
from starlette.status import HTTP_200_OK, HTTP_201_CREATED, HTTP_404_NOT_FOUND, HTTP_409_CONFLICT


@pytest.mark.asyncio
@pytest.mark.usefixtures(
    "db_sync_schema", "db_sync_model_initialized", "db_async_schema", "db_async_model_initialized"
)
class BaseTestController:
    """A class testing controllers.

    Attributes:
        name:   The name of the endpoint object to be tested.
        path:   The path to the endpoint in the API.
        attrs:  A dictionary of attributes needed to create an object in
                the API. Values can be tuples of other controller test
                classes and an item name to create such objects and use
                the respective items in the result.
        unique: Whether or not objects with the same attributes can
                exist more than once. If it is a string, check whether
                it is in the error detail (case-insensitively). If it is
                a regular expression pattern object, check if it can
                matched anywhere in the error detail string.

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
                    client, add_attrs={"foo_id": bar1["id"]}
                )
                result = response.json()
                bar2 = result["bar"]

                ...
    """

    name = None
    path = None
    attrs = {}
    unique = False

    @property
    def name_plural(self):
        """This is used for returning collections of objects from the API."""
        return self.name + "s"

    @classmethod
    async def _create_obj(cls, client, add_attrs: dict = None):
        attrs = {**(cls.attrs or {}), **(add_attrs or {})}

        for name, value in attrs.items():
            try:
                subcls, item = value
            except (TypeError, ValueError):
                pass
            else:
                if isinstance(subcls, type) and issubclass(subcls, BaseTestController):
                    subresponse = await subcls._create_obj(client)
                    subresult = subresponse.json()
                    value = subresult[subcls.name]
                    for elem in item.split("."):
                        value = value[elem]
                attrs[name] = value

        response = await client.post(cls.path, json=attrs)
        return response

    @classmethod
    def _verify_item(cls, item, attrs=None):
        if not attrs:
            attrs = cls.attrs
        # The `id` attribute of any created object must be 1 because no objects exist in the
        # database before running this test, the `db_*_model_initialized` fixtures take care of it.
        assert item["id"] == 1
        for key, value in attrs.items():
            try:
                subcls, _ = cls.attrs[key]
            except (TypeError, ValueError):
                pass
            else:
                if isinstance(subcls, type) and issubclass(subcls, BaseTestController):
                    # skip verifying objects this one depends on
                    continue
            assert item[key] == value

    async def test_create_obj(self, client):
        """Test that objects can be created on the API endpoint."""
        response = await self._create_obj(client)
        assert response.status_code == HTTP_201_CREATED
        result = response.json()
        self._verify_item(result[self.name])

    @classmethod
    def _add_attrs_from_response(cls, response):
        result = response.json()
        obj = result[cls.name]

        retval = {}
        for name, value in cls.attrs.items():
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
            client, add_attrs=self._add_attrs_from_response(create_response)
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

        response = await client.get(f"{self.path}/1")

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
        obj = result[self.name_plural][0]
        assert obj["id"] == 1
        attrs = {**self.attrs, **self._add_attrs_from_response(create_response)}
        self._verify_item(obj, attrs=attrs)

    @pytest.mark.parametrize("testcase", ("found", "not found"))
    async def test_delete_obj(self, client, testcase):
        if testcase != "not found":
            await self._create_obj(client)

        response = await client.delete(f"{self.path}/1")

        if testcase == "found":
            assert response.status_code == HTTP_200_OK
        else:
            assert response.status_code == HTTP_404_NOT_FOUND
