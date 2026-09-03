# API Contract Validation Report: case_09

## Summary
2 violations found in `POST /webhooks`. The endpoint lacks required security header validation and contains a type mismatch in the request body schema.

## Violations Found
1. **SECURITY_MISSING**: Missing required `X-Webhook-Secret` header validation.
2. **TYPE_MISMATCH**: Request body field `payload` is typed as `Any` instead of `object`.

## Details

### 1. Missing Security Header
*   **Endpoint**: `POST /webhooks`
*   **Spec Requirement**: Header parameter `X-Webhook-Secret` is **required** (type: string).
*   **Current Implementation**: The `receive_webhook` function does not declare or validate this header.
*   **Impact**: High security risk. The endpoint accepts unauthenticated webhook payloads, allowing potential spoofing or unauthorized data injection.
*   **Fix**:
    1.  Add `x_webhook_secret: str = Header(..., alias="X-Webhook-Secret")` to the function signature.
    2.  Implement logic to verify the secret against a trusted source (e.g., environment variable or database) before processing the body.

### 2. Type Mismatch in Payload
*   **Endpoint**: `POST /webhooks`
*   **Spec Requirement**: Field `payload` in the request body must be type `object`.
*   **Current Implementation**: Pydantic model `WebhookPayload` defines `payload` as `Any`.
*   **Impact**: Medium. Lack of strict typing prevents automatic validation of the payload structure, potentially allowing malformed data to pass through to downstream services.
*   **Fix**:
    1.  Define a specific Pydantic model (e.g., `WebhookData`) representing the expected object structure.
    2.  Update `WebhookPayload` to use this model: `payload: WebhookData`.

## Recommendation
Update the `receive_webhook` endpoint to enforce the `X-Webhook-Secret` header and replace the `Any` type for `payload` with a concrete Pydantic model to ensure strict contract compliance.