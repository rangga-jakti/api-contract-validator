"""
Tool: Code Analyzer
Uses Python AST to extract endpoint definitions from FastAPI service code.
Does NOT execute the code — pure static analysis.

This gives the agent precise ground truth about what the code actually does,
preventing LLM hallucination about code behavior.
"""

import ast
import re
from typing import Any


def analyze_code(code_content: str) -> dict:
    """
    Parse Python FastAPI service code using AST and extract:
    - All registered endpoints (method, path)
    - For each endpoint: function signature, Pydantic models used, return patterns
    - Response status codes from decorators or HTTPException raises

    Returns structured dict the agent can compare against spec.
    """
    try:
        tree = ast.parse(code_content)
    except SyntaxError as e:
        return {"error": f"Syntax error in code: {str(e)}", "endpoints": [], "models": {}}

    analyzer = _FastAPIAnalyzer()
    analyzer.visit(tree)

    # Extract module-level dict/list variables (e.g. PRODUCTS = [...])
    module_vars = _extract_module_variables(tree)
    
    # Extract ALL dict keys returned anywhere in module (catches helper functions)
    all_return_keys = _extract_all_return_dict_keys(tree)
    
    # Extract ALL HTTPExceptions from entire module (catches helper validation functions)
    all_http_exceptions = _extract_all_http_exceptions(tree)
    
    # Extract string enum values (signals potential TYPE_MISMATCH if spec expects integer)
    enum_string_values = _extract_enum_string_values(tree)

    # Enrich endpoints with field info from module vars and helper functions
    for ep in analyzer.endpoints:
        if not ep["return_fields"]:
            ep["module_var_fields"] = _find_relevant_var_fields(module_vars, ep["path"])
        else:
            ep["module_var_fields"] = []
        # Always attach all return keys from module for deeper analysis
        ep["all_module_return_keys"] = all_return_keys

    return {
        "endpoints": analyzer.endpoints,
        "models": analyzer.models,
        "module_variables": module_vars,
        "all_return_keys": all_return_keys,
        "all_http_exceptions": all_http_exceptions,
        "enum_string_values": enum_string_values,
        "endpoint_paths": [f"{e['method']} {e['path']}" for e in analyzer.endpoints],
        "raw_code": code_content,
    }


def _extract_all_return_dict_keys(tree: ast.Module) -> list:
    """Extract all string keys from dict literals returned anywhere in the module.
    Catches violations hidden in helper functions like _build_product_record().
    """
    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and node.value:
            if isinstance(node.value, ast.Dict):
                for key in node.value.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        keys.add(key.value)
    return list(keys)


def _extract_all_http_exceptions(tree: ast.Module) -> list:
    """Extract ALL HTTPException raises from entire module, including helper functions.
    Catches violations where validation logic is in a separate function.
    """
    exceptions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and node.exc:
            exc = node.exc
            if isinstance(exc, ast.Call):
                func_name = ""
                if isinstance(exc.func, ast.Name):
                    func_name = exc.func.id
                elif isinstance(exc.func, ast.Attribute):
                    func_name = exc.func.attr
                if "HTTPException" in func_name:
                    status_code = None
                    for kw in exc.keywords:
                        if kw.arg == "status_code" and isinstance(kw.value, ast.Constant):
                            status_code = kw.value.value
                    if not status_code and exc.args:
                        if isinstance(exc.args[0], ast.Constant):
                            status_code = exc.args[0].value
                    exceptions.append({"status_code": status_code})
    return exceptions


def _extract_enum_string_values(tree: ast.Module) -> list:
    """Extract string values from Enum classes — signals TYPE_MISMATCH if spec expects integer."""
    string_enum_values = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = [b.id if isinstance(b, ast.Name) else b.attr if isinstance(b, ast.Attribute) else ""
                     for b in node.bases]
            if "str" in bases or "Enum" in bases:
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        if isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                            string_enum_values.append(item.value.value)
    return string_enum_values


def _extract_module_variables(tree: ast.Module) -> dict:
    """Extract module-level list/dict variable assignments and their keys."""
    vars_found = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    var_name = target.id
                    fields = _get_dict_keys_from_value(node.value)
                    if fields:
                        vars_found[var_name] = fields
    return vars_found


def _get_dict_keys_from_value(node) -> list:
    """Extract string keys from a dict or list-of-dicts AST node."""
    keys = []
    if isinstance(node, ast.Dict):
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.append(key.value)
    elif isinstance(node, ast.List) and node.elts:
        # list of dicts — take keys from first element
        first = node.elts[0]
        if isinstance(first, ast.Dict):
            for key in first.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.append(key.value)
    return keys


def _find_relevant_var_fields(module_vars: dict, path: str) -> list:
    """Find fields from module variables likely used by an endpoint."""
    all_fields = []
    for var_name, fields in module_vars.items():
        all_fields.extend(fields)
    return list(set(all_fields))


class _FastAPIAnalyzer(ast.NodeVisitor):
    """AST visitor that extracts FastAPI endpoint and Pydantic model info."""

    HTTP_DECORATORS = {"get", "post", "put", "patch", "delete", "options", "head"}

    def __init__(self):
        self.endpoints = []
        self.models = {}  # Pydantic BaseModel subclasses
        self.current_function = None

    def visit_ClassDef(self, node: ast.ClassDef):
        """Detect Pydantic BaseModel subclasses and extract their fields."""
        base_names = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_names.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_names.append(base.attr)

        if "BaseModel" in base_names:
            fields = {}
            for item in node.body:
                if isinstance(item, ast.AnnAssign):
                    field_name = item.target.id if isinstance(item.target, ast.Name) else None
                    if not field_name:
                        continue

                    # Determine if field is optional (has default or uses Optional)
                    has_default = item.value is not None
                    type_str = _ast_type_to_str(item.annotation)
                    is_optional = (
                        "Optional" in type_str
                        or has_default
                        or "None" in type_str
                    )

                    # Get default value if present
                    default = None
                    if item.value is not None:
                        default = _ast_value_to_str(item.value)

                    fields[field_name] = {
                        "type": type_str,
                        "required": not is_optional,
                        "has_default": has_default,
                        "default": default,
                    }

            self.models[node.name] = {
                "fields": fields,
                "required_fields": [n for n, f in fields.items() if f["required"]],
                "optional_fields": [n for n, f in fields.items() if not f["required"]],
            }

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Detect FastAPI route handlers via decorators."""
        for decorator in node.decorator_list:
            endpoint_info = self._extract_route_decorator(decorator, node)
            if endpoint_info:
                self.endpoints.append(endpoint_info)
                break
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Detect async FastAPI route handlers."""
        for decorator in node.decorator_list:
            endpoint_info = self._extract_route_decorator(decorator, node)
            if endpoint_info:
                self.endpoints.append(endpoint_info)
                break
        self.generic_visit(node)

    def _extract_route_decorator(self, decorator, func_node: ast.FunctionDef) -> dict | None:
        """Extract route info from @app.get("/path") style decorators."""
        method = None
        path = None

        # Handle @app.METHOD("/path") or @router.METHOD("/path")
        if isinstance(decorator, ast.Call):
            func = decorator.func
            if isinstance(func, ast.Attribute) and func.attr in self.HTTP_DECORATORS:
                method = func.attr.upper()
                if decorator.args:
                    arg = decorator.args[0]
                    if isinstance(arg, ast.Constant):
                        path = arg.value

        if not method or not path:
            return None

        # Extract status_code from decorator kwargs
        declared_status_code = None
        for kw in (decorator.keywords if hasattr(decorator, "keywords") else []):
            if kw.arg == "status_code":
                if isinstance(kw.value, ast.Constant):
                    declared_status_code = kw.value.value

        # Extract function parameters (body model, path params, query params)
        func_params = _extract_function_params(func_node)

        # Extract return statements to infer response fields
        return_fields = _extract_return_fields(func_node)

        # Extract raised HTTP exceptions
        http_exceptions = _extract_http_exceptions(func_node)

        # Infer default status code
        if declared_status_code is None:
            if method == "POST":
                declared_status_code = 200  # FastAPI default is 200 even for POST unless specified
            elif method == "DELETE":
                declared_status_code = 200
            else:
                declared_status_code = 200

        return {
            "method": method,
            "path": path,
            "function_name": func_node.name,
            "declared_status_code": declared_status_code,
            "params": func_params,
            "return_fields": return_fields,
            "http_exceptions": http_exceptions,
        }


def _extract_function_params(func_node: ast.FunctionDef) -> dict:
    """Extract function signature parameters."""
    params = {
        "path_params": [],
        "query_params": [],
        "body_model": None,
        "header_params": [],
        "all_args": [],
    }

    path_param_pattern = re.compile(r"\{(\w+)\}")
    # We need path from context, so just collect all args
    for arg in func_node.args.args:
        if arg.arg in ("self", "cls"):
            continue
        type_str = _ast_type_to_str(arg.annotation) if arg.annotation else "unknown"
        params["all_args"].append({
            "name": arg.arg,
            "type": type_str,
        })

        # If type is a known Pydantic model reference, it's a body param
        if type_str not in ("int", "str", "float", "bool", "unknown", "Any") and \
           not type_str.startswith("Optional"):
            params["body_model"] = type_str

    # Check for Header() annotations in defaults
    for i, default in enumerate(func_node.args.defaults):
        if isinstance(default, ast.Call):
            if isinstance(default.func, ast.Name) and default.func.id == "Header":
                # Find which arg this default belongs to (defaults align from the right)
                arg_idx = len(func_node.args.args) - len(func_node.args.defaults) + i
                if arg_idx < len(func_node.args.args):
                    params["header_params"].append(
                        func_node.args.args[arg_idx].arg
                    )

    return params


def _extract_return_fields(func_node: ast.FunctionDef) -> list[str]:
    """Extract field names from return dict literals in a function."""
    fields = []
    for node in ast.walk(func_node):
        if isinstance(node, ast.Return) and node.value:
            if isinstance(node.value, ast.Dict):
                for key in node.value.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        fields.append(key.value)
    return list(set(fields))


def _extract_http_exceptions(func_node: ast.FunctionDef) -> list[dict]:
    """Find HTTPException raises in the function."""
    exceptions = []
    for node in ast.walk(func_node):
        if isinstance(node, ast.Raise) and node.exc:
            exc = node.exc
            if isinstance(exc, ast.Call):
                func_name = ""
                if isinstance(exc.func, ast.Name):
                    func_name = exc.func.id
                elif isinstance(exc.func, ast.Attribute):
                    func_name = exc.func.attr
                if "HTTPException" in func_name or "Exception" in func_name:
                    status_code = None
                    for kw in exc.keywords:
                        if kw.arg == "status_code" and isinstance(kw.value, ast.Constant):
                            status_code = kw.value.value
                    # Also check positional arg
                    if not status_code and exc.args:
                        if isinstance(exc.args[0], ast.Constant):
                            status_code = exc.args[0].value
                    exceptions.append({"type": func_name, "status_code": status_code})
    return exceptions


def _ast_type_to_str(annotation) -> str:
    """Convert AST annotation node to readable type string."""
    if annotation is None:
        return "unknown"
    if isinstance(annotation, ast.Name):
        return annotation.id
    if isinstance(annotation, ast.Constant):
        return str(annotation.value)
    if isinstance(annotation, ast.Attribute):
        return f"{_ast_type_to_str(annotation.value)}.{annotation.attr}"
    if isinstance(annotation, ast.Subscript):
        val = _ast_type_to_str(annotation.value)
        slice_val = _ast_type_to_str(annotation.slice)
        return f"{val}[{slice_val}]"
    if isinstance(annotation, ast.Tuple):
        parts = [_ast_type_to_str(e) for e in annotation.elts]
        return ", ".join(parts)
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        left = _ast_type_to_str(annotation.left)
        right = _ast_type_to_str(annotation.right)
        return f"{left} | {right}"
    return "unknown"


def _ast_value_to_str(value_node) -> str:
    """Convert AST value node to string representation."""
    if isinstance(value_node, ast.Constant):
        return repr(value_node.value)
    if isinstance(value_node, ast.Name):
        return value_node.id
    return "..."


def format_code_summary(analyzed: dict) -> str:
    """Format analyzed code as readable text for the agent."""
    lines = []
    for ep in analyzed["endpoints"]:
        lines.append(f"\nENDPOINT: {ep['method']} {ep['path']}")
        lines.append(f"  Function: {ep['function_name']}")
        lines.append(f"  Declared status code: {ep['declared_status_code']}")

        params = ep["params"]
        if params["body_model"]:
            lines.append(f"  Body model: {params['body_model']}")
        if params["all_args"]:
            arg_strs = [f"{a['name']}:{a['type']}" for a in params["all_args"]]
            lines.append(f"  Args: {', '.join(arg_strs)}")
        if params["header_params"]:
            lines.append(f"  Header params: {params['header_params']}")

        if ep["return_fields"]:
            lines.append(f"  Return fields: {ep['return_fields']}")
        elif ep.get("module_var_fields"):
            lines.append(f"  Return fields (from module vars): {ep['module_var_fields']}")
        if ep.get("all_module_return_keys"):
            lines.append(f"  All dict keys returned in module: {ep['all_module_return_keys']}")

        if ep["http_exceptions"]:
            for exc in ep["http_exceptions"]:
                lines.append(f"  Raises: {exc['type']}(status={exc['status_code']})")

    # Module-wide signals
    if analyzed.get("all_http_exceptions"):
        codes = [str(e["status_code"]) for e in analyzed["all_http_exceptions"]]
        lines.append(f"\nMODULE-WIDE HTTPExceptions (incl. helper functions): {codes}")
        lines.append("  NOTE: If spec says requestBody required=false but code raises 400 -> BEHAVIOR_CONTRADICTION")

    if analyzed.get("enum_string_values"):
        lines.append(f"MODULE-WIDE String enum values: {analyzed['enum_string_values']}")
        lines.append("  NOTE: If spec declares related field as type:integer, this is TYPE_MISMATCH")

    if analyzed["models"]:
        lines.append("\nPYDANTIC MODELS:")
        for model_name, model_info in analyzed["models"].items():
            lines.append(f"  {model_name}:")
            lines.append(f"    Required: {model_info['required_fields']}")
            lines.append(f"    Optional: {model_info['optional_fields']}")
            for fname, finfo in model_info["fields"].items():
                lines.append(f"    Field '{fname}': type={finfo['type']}, required={finfo['required']}, default={finfo['default']}")

    return "\n".join(lines)


if __name__ == "__main__":
    import os
    test_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "data", "services", "case_01.py")
    with open(test_path) as f:
        code = f.read()

    result = analyze_code(code)
    print(format_code_summary(result))
