import re
from datetime import timedelta
from functools import lru_cache
from typing import Type

from pydantic.types import _registered


class _TimeDelta(timedelta):
    strip_whitespace = True
    to_lower = True
    needs_sign = False
    allow_negative = True
    allow_dimensionless_seconds = True

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
    @lru_cache
    def validate(cls, v):
        if isinstance(v, timedelta):
            return v

        if cls.allow_dimensionless_seconds:
            if isinstance(v, (int, float)):
                return timedelta(seconds=v)
            if not isinstance(v, str):
                raise TypeError(f"input value {v!r} must be a string, an integer or a float")
            if v.isdigit():
                return timedelta(seconds=int(v))
        elif not isinstance(v, str):
            raise TypeError("input value must be a string")
        m = cls.timedelta_re.fullmatch(v.strip().lower())
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
    allow_dimensionless_seconds: bool = True,
) -> Type[timedelta]:
    namespace = {
        "strip_whitespace": strip_whitespace,
        "to_lower": to_lower,
        "needs_sign": needs_sign,
        "allow_negative": allow_negative,
        "allow_dimensionless_seconds": allow_dimensionless_seconds,
    }
    return _registered(type("TimeDeltaValue", (_TimeDelta,), namespace))


ConfigTimeDelta = readable_timedelta(allow_negative=False)
APITimeDelta = readable_timedelta(needs_sign=True, allow_dimensionless_seconds=False)
