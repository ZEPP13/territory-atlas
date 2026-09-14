"""A deliberately small JSON Schema (draft-07 subset) validator, stdlib only.

Why not a library: the project runs on a stock macOS Python with no third-party packages,
and a reviewer can read all of this in a few minutes. The trade-off is handled explicitly:
`check_schema` REJECTS any keyword this validator does not implement, so a schema can never
contain a constraint that silently goes unchecked.
"""
import json
import os
import re
from datetime import datetime

from . import SCHEMAS

SUPPORTED = {"type", "enum", "const", "required", "properties", "additionalProperties", "items",
             "minItems", "maxItems", "minLength", "maxLength", "pattern", "minimum", "maximum",
             "format", "$ref"}
ANNOTATIONS = {"$schema", "$id", "title", "description", "definitions", "default", "examples"}


class SchemaError(Exception):
    """The schema itself uses something this validator cannot enforce."""


def _type_ok(value, t):
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "boolean":
        return isinstance(value, bool)
    if t == "string":
        return isinstance(value, str)
    if t == "object":
        return isinstance(value, dict)
    if t == "array":
        return isinstance(value, list)
    if t == "null":
        return value is None
    raise SchemaError(f"unknown type {t!r}")


def _format_ok(value, fmt):
    if fmt == "date-time":
        if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$", value):
            return False
        try:
            datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
            return True
        except ValueError:
            return False
    if fmt == "date":
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return True
        except ValueError:
            return False
    raise SchemaError(f"unsupported format {fmt!r}")


def check_schema(schema, path="#"):
    """Walk a schema and refuse any keyword this validator does not enforce."""
    if not isinstance(schema, dict):
        raise SchemaError(f"{path}: schema must be an object")
    for k, v in schema.items():
        if k in ANNOTATIONS:
            if k == "definitions":
                for name, sub in v.items():
                    check_schema(sub, f"{path}/definitions/{name}")
            continue
        if k not in SUPPORTED:
            raise SchemaError(f"{path}: keyword {k!r} is not supported by wartable.schema")
        if k == "properties":
            for name, sub in v.items():
                check_schema(sub, f"{path}/properties/{name}")
        elif k in ("items",) or (k == "additionalProperties" and isinstance(v, dict)):
            check_schema(v, f"{path}/{k}")
        elif k == "format":
            _format_ok("2000-01-01T00:00:00Z" if v == "date-time" else "2000-01-01", v)


def validate(value, schema, root=None, path="$"):
    """Return a list of human-readable error strings. Empty list means valid."""
    root = root if root is not None else schema
    errors = []
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/definitions/"):
            raise SchemaError(f"only local #/definitions refs are supported, got {ref!r}")
        return validate(value, root["definitions"][ref.split("/")[-1]], root, path)
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(value, t) for t in types):
            return [f"{path}: expected {'/'.join(types)}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not one of {schema['enum']}")
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: must equal {schema['const']!r}")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: longer than {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: does not match {schema['pattern']}")
        if "format" in schema and not _format_ok(value, schema["format"]):
            errors.append(f"{path}: not a valid {schema['format']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum {schema['maximum']}")
    if isinstance(value, dict):
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}: missing required {req!r}")
        props = schema.get("properties", {})
        for k, v in value.items():
            if k in props:
                errors += validate(v, props[k], root, f"{path}.{k}")
            else:
                ap = schema.get("additionalProperties", True)
                if ap is False:
                    errors.append(f"{path}: unexpected field {k!r}")
                elif isinstance(ap, dict):
                    errors += validate(v, ap, root, f"{path}.{k}")
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: more than {schema['maxItems']} items")
        if "items" in schema:
            for i, item in enumerate(value):
                errors += validate(item, schema["items"], root, f"{path}[{i}]")
    return errors


_CACHE = {}


def load(name):
    """Load and check a schema from 07-war-table/schemas/<name>.schema.json."""
    if name not in _CACHE:
        with open(os.path.join(SCHEMAS, f"{name}.schema.json")) as fh:
            s = json.load(fh)
        check_schema(s)
        _CACHE[name] = s
    return _CACHE[name]
