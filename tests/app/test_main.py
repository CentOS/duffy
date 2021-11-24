import pytest

from duffy.app.main import app


class TestMain:
    @pytest.mark.parametrize(
        "path",
        (
            "/api/v1/projects",
            "/api/v1/sessions",
        ),
    )
    def test_paths(self, path):
        assert any(r.path == path for r in app.routes)
