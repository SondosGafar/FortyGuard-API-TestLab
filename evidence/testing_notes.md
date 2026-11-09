
# FortyGuard API Evaluation

## Test 01 — Official Quickstart Example

Endpoint: POST /v1/heatmap

Test: Submit the polygon and date provided in the
official FortyGuard Quickstart documentation.

Expected:
Successful task submission with an activity_id,
assuming the example is supported by the account.

Actual:
HTTP 400 Bad Request

Error code: OUT_OF_COVERAGE
Field: polygon_aoi

Observation:
The official Quickstart example uses a location in
New York City, but the API rejected the request as
outside its supported geographic coverage.

Recommendation:
Provide an example verified to work with Free-plan
access, or clearly document geographic restrictions
for sample requests.

Status: Documentation / onboarding issue
(coverage restrictions require confirmation)
