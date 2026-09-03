# API Contract Validation Report: case_07

## Summary
2 high-confidence violations found in `GET /reports`. The implementation uses `offset` where the specification mandates `page` for both query parameters and response fields.

## Violations Found
1. **PARAM_NAME_MISMATCH**: Query parameter `offset` used instead of `page`.
2. **FIELD_NAME_MISMATCH**: Response field `offset` returned instead of `page`.

## Details

### 1. Query Parameter Mismatch
*   **Endpoint**: `GET /reports`
*   **Spec Requirement**: Accepts optional query parameter `page` (integer).
*   **Current Implementation**: Function `list_reports` accepts argument `offset` (int).
*   **Impact**: Clients sending `?page=2` will be ignored or cause errors; clients sending `?offset=2` will fail validation against the spec.
*   **Fix**: Rename the function argument from `offset` to `page`. Ensure the internal logic maps this value correctly if the backend still requires an offset calculation (e.g., `offset = (page - 1) * limit`).

### 2. Response Field Mismatch
*   **Endpoint**: `GET /reports`
*   **Spec Requirement**: Response JSON must include field `page` (integer).
*   **Current Implementation**: Returns field `offset` in the response body.
*   **Impact**: Clients parsing the response for `page` will receive `undefined`/`null`, breaking pagination UIs or logic.
*   **Fix**: Rename the response key from `offset` to `page` in the serialization layer or response model.

## Recommendation
Refactor `GET /reports` to strictly adhere to the `page`-based pagination contract defined in the spec. Update both the input parameter name and the output field name from `offset` to `page`, and add integration tests to verify the exact JSON structure matches the specification.