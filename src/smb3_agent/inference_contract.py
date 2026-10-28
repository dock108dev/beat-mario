"""Shared closed-schema validation for untrusted model proposals."""
import math


class InferenceError(ValueError):
    pass


def validate_object(value, schema):
    """Validate the small, closed role schemas without trusting server enforcement."""
    kind = schema["type"]
    if kind == "object":
        if not isinstance(value, dict) or set(value) != set(schema["properties"]):
            raise ValueError("Unexpected result fields")
        for key, subschema in schema["properties"].items():
            validate_object(value[key], subschema)
    elif kind == "array":
        if not isinstance(value, list) or not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 64):
            raise ValueError("Invalid array")
        for item in value:
            validate_object(item, schema["items"])
    elif kind == "string":
        if not isinstance(value, str) or len(value) > schema.get("maxLength", 2000):
            raise ValueError("Invalid string")
    elif kind == "integer":
        if type(value) is not int or not schema.get("minimum", 0) <= value <= schema.get("maximum", 999):
            raise ValueError("Invalid integer")
    elif kind == "boolean":
        if type(value) is not bool:
            raise ValueError("Invalid boolean")
    elif kind == "number":
        if type(value) not in (int, float) or not math.isfinite(value) or not schema.get("minimum", -math.inf) <= value <= schema.get("maximum", math.inf):
            raise ValueError("Invalid number")
    elif kind not in {"object", "array", "string", "integer"}:
        raise ValueError("Unsupported schema type")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError("Invalid enum")
