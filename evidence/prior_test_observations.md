# FortyGuard — Prior Evaluation Findings

**Evidence basis:** Manual API requests, local terminal outputs, and dashboard observations recorded on November 9, 2026. These findings are included for traceability and **were not re-executed within the API Test Lab**. Original screenshots and request logs may be supplied as separate supporting evidence.

| Test | Observed result | Interpretation |
| --- | --- | --- |
| Official New York heatmap Quickstart | HTTP 400, `OUT_OF_COVERAGE`, `polygon_aoi` | Sample location/date was rejected for tested account; recommend explicitly supported example or clearer coverage warning |
| Phoenix heatmap submission | HTTP 200 with an `activity_id` | API authentication and submission successful |
| Phoenix activity status | HTTP 200, `Completed`, result had `map_data` and `stats_data` | Asynchronous workflow and result data retrieval successful |
| No `api-key` header | HTTP 401 with actionable missing-header message | Correct authentication rejection |
| Valid key, empty JSON payload | HTTP 422, missing `polygon_aoi` and `date_time` in `detail` | Correct request validation; top-level message only mentioned first missing field |
| Nonexistent activity ID | HTTP 404, `details.message` explaining activity not found | Correct not-found handling |
| Intermittent name resolution error | `NameResolutionError` initially; later DNS resolved and requests succeeded | **Not** evidence of an API defect; source unknown |

## API design / documentation recommendations

- Error envelopes vary between `message` and `details.message`; standardizing top-level fields would make client parsing simpler.
- The Quickstart sample returned `OUT_OF_COVERAGE` with the evaluation account; a guaranteed supported sample, or an explicit note that examples may be rejected depending on coverage, would help first-time developers.
- Environmental Parameters: document missing values as `null`, distinguish from zero, and clarify which analyses are covered by plans.
- Heat Intelligence's supplied documentation says the required `temperature` value is **Fahrenheit** but describes the `date` as the date for the supplied **Celsius** temperature. Clarify this wording to avoid unit mistakes.
- Satellite endpoint documentation mentions legacy `orignal_image` (typo); display one canonical response field and explain aliases.

## Dashboard observations (separate from API)

- Successful workflows: heatmap creation, time-series simulation, environmental tile analysis, map comparison, satellite segmentation, Heat Intelligence report, Time of Measure and Exceedance analysis.
- Potential navigation issue: completed welcome modal reappeared on returning from comparison; on one attempt the state dropdown appeared beneath the modal. Refreshing improved dropdown placement but did not dismiss onboarding.
- Tutorial navigation was confusing after its related sidebar was closed using Esc, and exiting tile-capture mode was not straightforward.
- Email notification options were selected for comparison and Heat Intelligence, but delivery was not observed during the verification window. As delivery logs were unavailable, this finding remains **unconfirmed**.
- Temperature unit switch from Fahrenheit to Celsius did not persist when leaving and returning to map controls; perhaps a transient display option, but persistence could be clearer.

**Assessment boundary:** Model accuracy and notification delivery were not independently verified; observations in these areas are not classified as confirmed defects.
