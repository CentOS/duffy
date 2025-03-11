import datetime as dt
import re
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Union

from pydantic import (
    GetCoreSchemaHandler,
    PlainSerializer,
    TypeAdapter,
    WithJsonSchema,
    WrapValidator,
)
from typing_extensions import Annotated, _AnnotatedAlias


@dataclass(frozen=True)
class CustomTimeDelta:
    strip_whitespace: bool = True
    to_lower: bool = True
    needs_sign: bool = False
    allow_negative: bool = True
    allow_dimensionless_seconds: bool = True
    serialize_to_seconds: bool = False

    @cached_property
    def timedelta_re(self) -> re.Pattern:
        sign = "+-" if self.allow_negative else "+"
        needs_sign = "" if self.needs_sign else "?"
        return re.compile(
            rf"(?P<sign>[{sign}]){needs_sign}(?!\s*$)"
            + r"(?:\s*(?P<weeks>\d+)w)?"
            + r"(?:\s*(?P<days>\d+)d)?"
            + r"(?:\s*(?P<hours>\d+)h)?"
            + r"(?:\s*(?P<minutes>\d+)m)?"
            + r"(?:\s*(?P<seconds>\d+)s)?"
            + r"(?:\s*(?P<milliseconds>\d+)ms)?"
        )

    def validate(self, v: Union[str, Any], handler: GetCoreSchemaHandler) -> dt.timedelta:
        if isinstance(v, dt.timedelta):
            return handler(v)

        if self.allow_dimensionless_seconds:
            if isinstance(v, (int, float)):
                return dt.timedelta(seconds=v)
            if not isinstance(v, str):
                raise TypeError(f"input value {v!r} must be a string, an integer or a float")
            if v.isdigit():
                return dt.timedelta(seconds=int(v))
        elif not isinstance(v, str):
            raise TypeError("input value must be a string")

        if self.strip_whitespace:
            v = v.strip()

        if self.to_lower:
            v = v.lower()

        m = self.timedelta_re.fullmatch(v)
        if not m:
            raise ValueError("invalid timedelta format")

        sign = -1 if m.group("sign") == "-" else 1
        return dt.timedelta(
            weeks=sign * int(m.group("weeks") or 0),
            days=sign * int(m.group("days") or 0),
            hours=sign * int(m.group("hours") or 0),
            minutes=sign * int(m.group("minutes") or 0),
            seconds=sign * int(m.group("seconds") or 0),
            milliseconds=sign * int(m.group("milliseconds") or 0),
        )

    def serialize(self, v: dt.timedelta) -> Union[str, int, float]:
        total_seconds = v.total_seconds()

        if self.serialize_to_seconds:
            if not v.microseconds:
                return int(total_seconds)
            else:
                return total_seconds

        chunks: dict[str, int] = {}

        if total_seconds < 0:
            sign = "-"
            v = -v
        elif self.needs_sign:
            sign = "+"
        else:
            sign = ""

        weeks = v.days // 7
        days = v.days % 7
        if weeks:
            chunks["w"] = weeks
        if days:
            chunks["d"] = days

        hours = v.seconds // 3600
        hour_seconds = v.seconds % 3600
        minutes = hour_seconds // 60
        seconds = hour_seconds % 60

        if hours:
            chunks["h"] = hours
        if minutes:
            chunks["m"] = minutes
        if seconds:
            chunks["s"] = seconds

        milliseconds = v.microseconds // 1000
        if milliseconds:
            chunks["ms"] = milliseconds

        if not chunks:
            chunks["s"] = 0

        return sign + "".join(f"{value}{key}" for key, value in chunks.items())

    @cached_property
    def pydantic_type(self) -> _AnnotatedAlias:
        json_schema = TypeAdapter(dt.timedelta).json_schema()
        json_schema.update(examples=["+3h30m"])

        if self.needs_sign:
            json_schema.update(pattern=r"^[-+](\d+w)?(\d+d)?(\d+h)?(\d+m)?(\d+s)?(\d+ms)?$")
        else:
            json_schema.update(pattern=r"^[-+]?(\d+w)?(\d+d)?(\d+h)?(\d+m)?(\d+s)?(\d+ms)?$")
            json_schema["examples"].append("1h")

        if self.allow_negative:
            json_schema["examples"].append("-20m25s")

        return Annotated[
            dt.timedelta,
            WrapValidator(self.validate),
            PlainSerializer(self.serialize),
            WithJsonSchema(json_schema),
        ]


ConfigTimeDelta = CustomTimeDelta(allow_negative=False, serialize_to_seconds=True).pydantic_type
APITimeDelta = CustomTimeDelta(needs_sign=True, allow_dimensionless_seconds=False).pydantic_type
