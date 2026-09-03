"""
Ground truth for all 10 evaluation cases.
Each case defines the known violations (true positives).
Used to compute Precision, Recall, and F1 for both baseline and agent.

Violation types:
  - MISSING_REQUIRED_PARAM   : spec requires a field/param, code makes it optional/absent
  - FIELD_NAME_MISMATCH      : spec and code use different field names
  - STATUS_CODE_MISMATCH     : different HTTP status code than spec declares
  - UNDOCUMENTED_ENDPOINT    : endpoint in code not present in spec
  - RESPONSE_FIELD_RENAME    : response body field name differs from spec
  - BEHAVIOR_CONTRADICTION   : code behavior contradicts spec semantics
  - PARAM_NAME_MISMATCH      : query/path param names differ
  - SECURITY_MISSING         : required security mechanism absent in code
  - TYPE_MISMATCH            : field type in code differs from spec schema type
"""

GROUND_TRUTH = {
    "case_01": {
        "has_violations": True,
        "violations": [
            {
                "type": "MISSING_REQUIRED_PARAM",
                "location": "POST /users > requestBody > email",
                "description": "spec marks 'email' as required, code defines it as Optional with default None"
            }
        ]
    },
    "case_02": {
        "has_violations": True,
        "violations": [
            {
                "type": "FIELD_NAME_MISMATCH",
                "location": "GET /products > response > items > price",
                "description": "spec defines field 'price', code returns field 'cost'"
            }
        ]
    },
    "case_03": {
        "has_violations": True,
        "violations": [
            {
                "type": "STATUS_CODE_MISMATCH",
                "location": "DELETE /orders/{order_id} > response",
                "description": "spec declares 204 No Content, code returns 200 with a response body"
            }
        ]
    },
    "case_04": {
        "has_violations": True,
        "violations": [
            {
                "type": "UNDOCUMENTED_ENDPOINT",
                "location": "GET /health",
                "description": "endpoint GET /health exists in code but is not documented in the OpenAPI spec"
            }
        ]
    },
    "case_05": {
        "has_violations": True,
        "violations": [
            {
                "type": "RESPONSE_FIELD_RENAME",
                "location": "POST /auth/login > response > token",
                "description": "spec defines response field 'token', code returns 'access_token'"
            }
        ]
    },
    "case_06": {
        "has_violations": True,
        "violations": [
            {
                "type": "BEHAVIOR_CONTRADICTION",
                "location": "PUT /users/{user_id} > requestBody",
                "description": "spec marks requestBody as required:false (optional), but code raises HTTP 400 when no fields are provided"
            }
        ]
    },
    "case_07": {
        "has_violations": True,
        "violations": [
            {
                "type": "PARAM_NAME_MISMATCH",
                "location": "GET /reports > query params",
                "description": "spec defines query params 'page' and 'limit', code uses 'offset' and 'count'"
            }
        ]
    },
    "case_08": {
        "has_violations": False,
        "violations": []  # TRUE NEGATIVE: fully compliant service
    },
    "case_09": {
        "has_violations": True,
        "violations": [
            {
                "type": "SECURITY_MISSING",
                "location": "POST /webhooks > parameters > X-Webhook-Secret",
                "description": "spec requires X-Webhook-Secret header (required:true), code does not validate it at all"
            }
        ]
    },
    "case_10": {
        "has_violations": True,
        "violations": [
            {
                "type": "TYPE_MISMATCH",
                "location": "GET /users/{user_id}/permissions > response > permissions > resources > access_level",
                "description": "spec declares access_level as type:integer, code returns a string value ('write', 'read')"
            }
        ]
    },
}

def get_all_true_violations():
    """Returns list of (case_id, violation_type) tuples for all known violations."""
    result = []
    for case_id, data in GROUND_TRUTH.items():
        for v in data["violations"]:
            result.append((case_id, v["type"]))
    return result

def get_true_negative_cases():
    """Returns list of case_ids that have no violations."""
    return [c for c, d in GROUND_TRUTH.items() if not d["has_violations"]]

if __name__ == "__main__":
    total_violations = sum(len(d["violations"]) for d in GROUND_TRUTH.values())
    total_cases = len(GROUND_TRUTH)
    violations_cases = sum(1 for d in GROUND_TRUTH.values() if d["has_violations"])
    print(f"Total cases       : {total_cases}")
    print(f"Cases w/violations: {violations_cases}")
    print(f"True negatives    : {total_cases - violations_cases}")
    print(f"Total violations  : {total_violations}")
    print()
    for case_id, data in GROUND_TRUTH.items():
        status = "VIOLATION" if data["has_violations"] else "CLEAN"
        print(f"  [{status}] {case_id}: {len(data['violations'])} violation(s)")
