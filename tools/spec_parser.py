"""
Tool: Spec Parser
Extracts a structured contract representation from an OpenAPI 3.0 YAML/JSON spec.
Uses pure Python (yaml + stdlib) — no LLM call needed here.
This gives the agent precise, unambiguous facts about what the spec declares.
"""

import yaml
from typing import Any


def parse_spec(spec_content: str) -> dict:
    """
    Parse an OpenAPI 3.0 YAML spec and return a structured contract dict.

    Returns:
        {
          "endpoints": [
            {
              "method": "POST",
              "path": "/users",
              "request_body": {
                "required": True,
                "required_fields": ["email", "username"],
                "optional_fields": [],
                "all_fields": {"email": {"type": "string"}, ...}
              },
              "path_params": [{"name": "id", "required": True, "type": "integer"}],
              "query_params": [{"name": "page", "required": False, "type": "integer"}],
              "header_params": [{"name": "X-Secret", "required": True, "type": "string"}],
              "responses": {
                "201": {
                  "fields": {"id": {"type": "integer"}, ...}
                }
              }
            },
            ...
          ],
          "raw": <original parsed yaml dict>
        }
    """
    try:
        spec = yaml.safe_load(spec_content)
    except yaml.YAMLError as e:
        return {"error": f"Failed to parse YAML: {str(e)}", "endpoints": []}

    endpoints = []
    paths = spec.get("paths", {})

    for path, path_item in paths.items():
        for method in ["get", "post", "put", "patch", "delete", "options", "head"]:
            operation = path_item.get(method)
            if not operation:
                continue

            endpoint = {
                "method": method.upper(),
                "path": path,
                "summary": operation.get("summary", ""),
                "request_body": None,
                "path_params": [],
                "query_params": [],
                "header_params": [],
                "responses": {},
            }

            # Parse parameters (path, query, header)
            params = operation.get("parameters", [])
            for param in params:
                param_info = {
                    "name": param.get("name", ""),
                    "required": param.get("required", False),
                    "type": _extract_type(param.get("schema", {})),
                }
                location = param.get("in", "")
                if location == "path":
                    endpoint["path_params"].append(param_info)
                elif location == "query":
                    endpoint["query_params"].append(param_info)
                elif location == "header":
                    endpoint["header_params"].append(param_info)

            # Parse request body
            rb = operation.get("requestBody")
            if rb:
                rb_required = rb.get("required", False)
                content = rb.get("content", {})
                schema = {}
                for media_type in ["application/json", "application/x-www-form-urlencoded"]:
                    if media_type in content:
                        schema = content[media_type].get("schema", {})
                        break

                required_fields = schema.get("required", [])
                properties = schema.get("properties", {})

                endpoint["request_body"] = {
                    "required": rb_required,
                    "required_fields": required_fields,
                    "optional_fields": [f for f in properties if f not in required_fields],
                    "all_fields": {
                        k: {"type": _extract_type(v), "raw": v}
                        for k, v in properties.items()
                    },
                }

            # Parse responses
            responses = operation.get("responses", {})
            for status_code, response_obj in responses.items():
                resp_fields = {}
                content = response_obj.get("content", {})
                for media_type in ["application/json"]:
                    if media_type in content:
                        schema = content[media_type].get("schema", {})
                        resp_fields = _extract_schema_fields(schema)
                        break

                endpoint["responses"][str(status_code)] = {
                    "description": response_obj.get("description", ""),
                    "fields": resp_fields,
                }

            endpoints.append(endpoint)

    return {
        "endpoints": endpoints,
        "raw": spec,
        "endpoint_paths": [f"{e['method']} {e['path']}" for e in endpoints],
    }


def _extract_type(schema: dict) -> str:
    """Extract a human-readable type string from a schema object."""
    if not schema:
        return "unknown"
    t = schema.get("type", "")
    fmt = schema.get("format", "")
    if fmt:
        return f"{t}({fmt})"
    if t == "array":
        items = schema.get("items", {})
        return f"array[{_extract_type(items)}]"
    if t == "object":
        return "object"
    return t or "unknown"


def _extract_schema_fields(schema: dict, prefix: str = "") -> dict:
    """
    Recursively extract field names and types from a schema.
    Returns flat dict: {"field_name": {"type": "...", "path": "..."}}
    For nested objects, uses dot notation: "permissions.resources.access_level"
    """
    fields = {}
    if not schema:
        return fields

    schema_type = schema.get("type", "object")

    if schema_type == "object":
        properties = schema.get("properties", {})
        for field_name, field_schema in properties.items():
            full_key = f"{prefix}.{field_name}" if prefix else field_name
            field_type = _extract_type(field_schema)
            fields[full_key] = {
                "type": field_type,
                "path": full_key,
                "raw_schema": field_schema,
            }
            # Recurse into nested objects
            if field_schema.get("type") == "object":
                nested = _extract_schema_fields(field_schema, full_key)
                fields.update(nested)
            # Recurse into array items if they're objects
            elif field_schema.get("type") == "array":
                items_schema = field_schema.get("items", {})
                if items_schema.get("type") == "object":
                    nested = _extract_schema_fields(items_schema, f"{full_key}[]")
                    fields.update(nested)

    elif schema_type == "array":
        items_schema = schema.get("items", {})
        if items_schema.get("type") == "object":
            nested = _extract_schema_fields(items_schema, prefix)
            fields.update(nested)

    return fields


def format_contract_summary(parsed: dict) -> str:
    """Format parsed contract as readable text for the agent."""
    lines = []
    for ep in parsed["endpoints"]:
        lines.append(f"\nENDPOINT: {ep['method']} {ep['path']}")

        if ep["path_params"]:
            lines.append("  Path params: " + ", ".join(
                f"{p['name']}({'required' if p['required'] else 'optional'}, {p['type']})"
                for p in ep["path_params"]
            ))

        if ep["query_params"]:
            lines.append("  Query params: " + ", ".join(
                f"{p['name']}({'required' if p['required'] else 'optional'}, {p['type']})"
                for p in ep["query_params"]
            ))

        if ep["header_params"]:
            lines.append("  Header params: " + ", ".join(
                f"{p['name']}({'required' if p['required'] else 'optional'}, {p['type']})"
                for p in ep["header_params"]
            ))

        if ep["request_body"]:
            rb = ep["request_body"]
            lines.append(f"  Request body: required={rb['required']}")
            if rb["required_fields"]:
                lines.append(f"    Required fields: {rb['required_fields']}")
            if rb["optional_fields"]:
                lines.append(f"    Optional fields: {rb['optional_fields']}")
            for fname, finfo in rb["all_fields"].items():
                lines.append(f"    Field '{fname}': type={finfo['type']}")

        for code, resp in ep["responses"].items():
            lines.append(f"  Response {code}: {resp['description']}")
            for fname, finfo in resp["fields"].items():
                lines.append(f"    Field '{fname}': type={finfo['type']}")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys, os
    test_spec_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   "data", "specs", "case_01.yaml")
    with open(test_spec_path) as f:
        content = f.read()

    parsed = parse_spec(content)
    print(f"Endpoints found: {len(parsed['endpoints'])}")
    print(format_contract_summary(parsed))
