import re
from datetime import timedelta
from typing import Type

from pydantic.types import _registered
from pydantic.validators import constr_lower, constr_strip_whitespace, strict_str_validator


class _TimeDelta(timedelta):
    strip_whitespace = True
    to_lower = True
    needs_sign = False
    allow_negative = True

    def __init_subclass__(cls):
        sign = "+-" if cls.allow_negative else "+"
        needs_sign = "" if cls.needs_sign else "?"
        cls.timedelta_re = re.compile(
            rf"(?P<sign>[{sign}]){needs_sign}(?!\s*$)"
            + r"(?:\s*(?P<weeks>\d+)w)?"
            + r"(?:\s*(?P<days>\d+)d)?"
            + r"(?:\s*(?P<hours>\d+)h)?"
            + r"(?:\s*(?P<minutes>\d+)m)?"
            + r"(?:\s*(?P<seconds>\d+)s)?"
            + r"(?:\s*(?P<milliseconds>\d+)ms)?"
        )

    @classmethod
    def __get_validators__(cls):
        yield strict_str_validator
        yield constr_strip_whitespace
        yield constr_lower
        yield cls.validate

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(examples=["+3h30m"])
        if cls.needs_sign:
            field_schema.update(pattern=r"^[-+](\d+w)?(\d+d)?(\d+h)?(\d+m)?(\d+s)?(\d+ms)?$")
        else:
            field_schema.update(pattern=r"^[-+]?(\d+w)?(\d+d)?(\d+h)?(\d+m)?(\d+s)?(\d+ms)?$")
            field_schema["examples"].append("1h")

        if cls.allow_negative:
            field_schema["examples"].append("-20m25s")

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError("input value must be a string")
        m = cls.timedelta_re.fullmatch(v)
        if not m:
            raise ValueError("invalid timedelta format")
        sign = -1 if m.group("sign") == "-" else 1
        return timedelta(
            weeks=sign * int(m.group("weeks") or 0),
            days=sign * int(m.group("days") or 0),
            hours=sign * int(m.group("hours") or 0),
            minutes=sign * int(m.group("minutes") or 0),
            seconds=sign * int(m.group("seconds") or 0),
            milliseconds=sign * int(m.group("milliseconds") or 0),
        )


def readable_timedelta(
    *,
    strip_whitespace: bool = True,
    to_lower: bool = True,
    needs_sign: bool = False,
    allow_negative: bool = True,
) -> Type[timedelta]:
    namespace = {
        "strip_whitespace": strip_whitespace,
        "to_lower": to_lower,
        "needs_sign": needs_sign,
        "allow_negative": allow_negative,
    }
    return _registered(type("TimeDeltaValue", (_TimeDelta,), namespace))


ConfigTimeDelta = readable_timedelta(allow_negative=False)
APITimeDelta = readable_timedelta(needs_sign=True)
