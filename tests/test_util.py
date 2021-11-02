import pytest

from duffy.util import camel_case_to_lower_with_underscores


@pytest.mark.parametrize(
    "camelcased,converted",
    (
        ("AssetType", "asset_type"),
        ("EXIFFieldType", "exif_field_type"),
        ("BlahEXIF", "blah_exif"),
    ),
)
def test_camel_case_to_lower_with_underscores(camelcased, converted):
    assert camel_case_to_lower_with_underscores(camelcased) == converted
