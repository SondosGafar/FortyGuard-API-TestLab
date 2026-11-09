"""FortyGuard Test Lab — local Streamlit interface for documented API workflows.
Run: streamlit run app.py
Live API requests are submitted only after explicit action through the interface.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

from heatmap_preview import inspect_geojson
from heatmap_layers import prepare_polygon_layer
from environmental_insights import environmental_view, requested_parameter_coverage

from fortyguard_client import (
    ENDPOINTS, TOTAL_ESTIMATED_CREDITS, activity_id_from, activity_state,
    api_call, check_status, default_payload, evidence_csv_bytes, evidence_records,
    record_evidence, sanitized_result, submit, summarize_result_data,
)

st.set_page_config(page_title="FortyGuard · API Test Lab", page_icon="🌡️", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown("""
<style>
.block-container {padding-top: 2rem; padding-bottom: 3rem; max-width: 1450px;}
[data-testid="stSidebar"] {border-right: 1px solid #27354A;}
.hero {background: linear-gradient(110deg,#15243D,#153B55 66%,#0E6077);border:1px solid #34516C;
    border-radius:22px;padding:30px 35px;margin:6px 0 24px;}
.hero h1 {font-size:2.3rem;letter-spacing:-.045em;margin:2px 0 8px;color:#F7FAFE;}
.hero p {color:#C7DAE8;font-size:1.04rem;max-width:740px;margin:0;}
.eyebrow {color:#7DD3FC;font-size:.77rem;font-weight:750;letter-spacing:.13em;text-transform:uppercase;}
.kpi {border:1px solid #2A3B53;background:#132237;padding:18px 20px;border-radius:16px;min-height:115px;}
.kpi small {display:block;color:#AABBD1;font-size:.8rem;margin-bottom:12px;}
.kpi strong {font-size:1.65rem;letter-spacing:-.04em;}
.muted-note {font-size:.84rem;color:#AEBECF;}
.stButton>button[kind="primary"] {border-radius:10px;}
[data-testid="stMetricValue"]{font-size:1.75rem;}
</style>
""", unsafe_allow_html=True)

if "last_body" not in st.session_state:
    st.session_state.last_body = None
if "last_endpoint" not in st.session_state:
    st.session_state.last_endpoint = None
if "last_http" not in st.session_state:
    st.session_state.last_http = None
if "last_activity" not in st.session_state:
    st.session_state.last_activity = ""
if "last_payload" not in st.session_state:
    st.session_state.last_payload = None
if "last_test_name" not in st.session_state:
    st.session_state.last_test_name = None
if "payload_by_activity" not in st.session_state:
    st.session_state.payload_by_activity = {}


def remember(name: str, http: int | None, body: dict, payload=None):
    st.session_state.last_endpoint = name
    st.session_state.last_test_name = name
    st.session_state.last_http = http
    st.session_state.last_body = body
    found_id = activity_id_from(body)
    if found_id:
        st.session_state.last_activity = found_id
        if payload is not None:
            st.session_state.payload_by_activity[found_id] = payload
    st.session_state.last_payload = (payload if payload is not None else
                                     st.session_state.payload_by_activity.get(found_id))


def save_test(name: str, method: str, path: str, payload, code, body, credits=0, notes=""):
    try:
        return record_evidence(name, method, path, payload, code, body,
                               estimate=credits, notes=notes)
    except OSError as exc:
        st.warning(f"Result received, but evidence could not be saved: {exc}")
        return None


def outcome_verdict(test_name: str | None, code: int | None, body: dict) -> tuple[str, str]:
    """Differentiate expected HTTP errors from failed request submissions."""
    expected_errors = {"missing_key": 401, "invalid_payload": 422, "invalid_activity": 404}
    if code is None:
        return "Transport error", "No HTTP response was received."
    if test_name in expected_errors:
        expected = expected_errors[test_name]
        if code == expected:
            return "Passed — expected rejection", f"The API returned HTTP {code}, as expected for this negative test."
        return "Unexpected response", f"Expected HTTP {expected}; received HTTP {code}."
    if not 200 <= code < 300:
        return "Request rejected", f"HTTP {code} — inspect the error details before interpreting the cause."
    status = activity_state(body)
    if status and status.lower() in ("failed", "error"):
        return "Activity failed", "The server reported a terminal activity failure."
    if status and status.lower() in ("completed", "succeeded"):
        return "Passed — activity completed", "The accepted task finished successfully. Inspect result contents separately."
    return "Submission accepted", "The server accepted the request; completion has not yet been verified."


def show_outcome(code, body, test_name=None):
    verdict, explanation = outcome_verdict(test_name, code, body)
    if verdict.startswith("Passed") or verdict == "Submission accepted":
        st.success(f"{verdict} · {explanation}")
    elif verdict in ("Transport error", "Activity failed"):
        st.error(f"{verdict} · {explanation}")
    else:
        st.warning(f"{verdict} · {explanation}")
    a, b = st.columns([1, 2])
    with a:
        st.metric("HTTP status", code if code is not None else "No response")
        st.metric("Activity status", activity_state(body) or "Not provided")
        if activity_id_from(body):
            st.code(activity_id_from(body), language=None)
    with b:
        st.caption("Sanitized preview · large geographic data, images and signed URLs omitted")
        st.json(sanitized_result(body), expanded=1)


def available_metrics(stats: dict):
    source = stats.get("Temperature_stats") or stats.get("temperature_stats") or {}
    if isinstance(source, dict):
        candidate = {k.lower().replace(" ", "_"): v for k, v in source.items()}
        fields = [("Minimum", "minimum"), ("Maximum", "maximum"),
                  ("Mean", "mean"), ("Std. dev.", "standard_deviation")]
        c = st.columns(4)
        for col, (label, key) in zip(c, fields):
            number = candidate.get(key)
            col.metric(label, f"{number:.2f}" if isinstance(number, (int, float)) else "—")


def show_segmentation_image(data, label: str):
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, str):
        return
    try:
        string = data.split(",", 1)[-1] if data.startswith("data:") else data
        if len(string) > 35_000_000:
            st.caption(f"{label} too large to preview")
            return
        decoded = base64.b64decode(string, validate=False)
        st.image(decoded, caption=label, use_column_width=True)
    except Exception:
        st.caption(f"{label} could not be decoded from the response")


def show_segments(segments: dict):
    rows = []
    for key, val in segments.items():
        if isinstance(val, (int, float)):
            rows.append({"Category": str(key), "Coverage %": float(val)})
        elif isinstance(val, dict):
            percentage = val.get("percentage", val.get("percent", val.get("value")))
            if isinstance(percentage, (int, float)):
                rows.append({"Category": str(key), "Coverage %": float(percentage)})
    if rows:
        df = pd.DataFrame(rows).sort_values("Coverage %", ascending=False)
        st.plotly_chart(px.bar(df, x="Coverage %", y="Category", orientation="h",
                               title="Class coverage (%)", template="plotly_dark"), use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)


def show_heatmap_points(map_data: dict):
    """Render GeoJSON polygons; do not synthesize unavailable temperatures."""
    coverage = prepare_polygon_layer(map_data)
    st.caption(f"GeoJSON returned: {coverage['total']:,} features · Polygon preview: {coverage['mapped']:,} features")
    if coverage["truncated"]:
        st.caption("Large response: preview is limited to the first 1,500 polygons.")
    if not coverage["rows"]:
        st.warning("No supported polygon geometries were available for a geographic preview.")
        return

    has_values = coverage["measured"] > 0
    if has_values:
        st.success(
            f"Numeric tile data detected in `{coverage['temperature_field']}` for "
            f"{coverage['measured']:,} polygons. Values are displayed as returned by the API. "
            "Confirm the field's units in the response metadata."
        )
    else:
        st.info(
            "No numeric per-tile temperature property could be identified. "
            "The shaded polygons below represent geographic coverage only, not temperature. "
            "Summary statistics remain available above."
        )
    df = pd.DataFrame(coverage["rows"])
    if has_values:
        plot_data = df[df["value"].notna()].copy()
        z_values = plot_data["value"].tolist()
        locations = plot_data["id"].tolist()
    else:
        z_values = [0] * len(df)
        locations = df["id"].tolist()
    field_name = coverage["temperature_field"] or "Coverage only"
    scale = "RdYlBu_r" if has_values else [[0, "#427a94"], [1, "#427a94"]]
    fig = go.Figure(go.Choroplethmapbox(
        geojson=coverage["geojson"], featureidkey="id", locations=locations,
        z=z_values, colorscale=scale, showscale=has_values,
        marker_opacity=0.62 if has_values else 0.4, marker_line_width=0.5,
        colorbar={"title": field_name} if has_values else None,
        hovertemplate=("Tile %{location}<br>Reported value %{z:.3f}<extra></extra>" if has_values
                       else "Tile %{location}<br>Coverage only<extra></extra>"),
    ))
    fig.update_layout(mapbox={"style": "open-street-map", "center": coverage["center"], "zoom": 12},
                      height=510, margin=dict(l=4, r=4, t=6, b=4),
                      paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
    if has_values and coverage["measured"] < coverage["mapped"]:
        st.caption("Some polygons do not contain a supported numeric field and are not temperature-colored.")
    with st.expander("GeoJSON field diagnostics"):
        scan = inspect_geojson(map_data)
        st.write("Property names in the first populated feature:", scan["sample_property_keys"] or "None")
        st.write("Recognized numeric property paths:", scan["numeric_paths"] or "None")
        st.write("Dominant property path:", coverage["temperature_field"] or "None")
        st.caption("Polygon geometry and provider data are not modified by this visualization.")


def show_environmental_results(result: dict):
    """Display point-level environmental data and timestamp-aligned measurements."""
    view = environmental_view(result)
    rows = view["rows"]
    st.subheader("Environmental Parameters · Point analysis")
    heading = st.columns(3)
    heading[0].metric("Location", f"{view['latitude']}, {view['longitude']}")
    heading[1].metric("Timezone", view["timezone"] or "Not supplied")
    heading[2].metric("Time steps", len(view["timestamps"]) or view["time_range"].get("count", "—"))
    st.caption("Reported location measurements, not a spatial heatmap. Missing values (`null` or `-999`) are shown as unavailable.")
    if not rows:
        st.info("No environmental measurement arrays are present in the completed result.")
        return

    payload = st.session_state.get("last_payload") or {}
    requested = payload.get("analysis") if isinstance(payload, dict) else None
    if requested:
        coverage = requested_parameter_coverage(rows, requested)
        if coverage["absent"]:
            st.warning("Some requested fields are absent: " + ", ".join(coverage["absent"]))
        else:
            st.success(f"All {len(coverage['present'])} requested parameter fields are present in the result.")
        if coverage["additional"]:
            st.caption(f"Response also includes {len(coverage['additional'])} additional fields; their presence alone does not establish a filtering defect.")
    key_priority = requested or ["heat_index_celsius", "relative_humidity_percent", "precipitation_mm"]
    chosen = [r for key in key_priority for r in rows if r["key"] == key]
    if not chosen:
        chosen = rows[:3]
    cards = st.columns(min(3, len(chosen)))
    for i, row in enumerate(chosen[:3]):
        metric_value = row["first"]
        formatted = f"{metric_value:,.2f} {row['unit']}" if metric_value is not None else "N/A"
        cards[i % len(cards)].metric(row["label"], formatted)
    if len(view["timestamps"]) > 1:
        plot_rows = []
        for item in rows:
            for idx, value in enumerate(item["values"]):
                if value is not None and idx < len(view["timestamps"]):
                    plot_rows.append({"Timestamp": view["timestamps"][idx],
                                      "Measurement": item["label"], "Value": value, "Unit": item["unit"]})
        if plot_rows:
            st.markdown("**Time-series measurements**")
            options = [r["key"] for r in rows if any(v is not None for v in r["values"])]
            if options:
                selected = st.selectbox("Measurement to chart", options,
                                        format_func=lambda key: next(r["label"] for r in rows if r["key"] == key))
                chosen_row = next(r for r in rows if r["key"] == selected)
                points = [{"Time": view["timestamps"][i], "Value": val} for i, val in enumerate(chosen_row["values"])
                          if i < len(view["timestamps"]) and val is not None]
                if points:
                    chart = px.line(pd.DataFrame(points), x="Time", y="Value", markers=True,
                                    title=f"{chosen_row['label']} ({chosen_row['unit']})", template="plotly_dark")
                    st.plotly_chart(chart, use_container_width=True)
    st.markdown("**Returned measurements**")
    table = []
    for item in rows:
        valid = [v for v in item["values"] if v is not None]
        table.append({"Field": item["key"], "Measurement": item["label"], "Unit": item["unit"] or "—",
                      "First value": valid[0] if valid else "N/A",
                      "Available": f"{item['available']} / {item['count']}"})
    st.dataframe(pd.DataFrame(table), hide_index=True, use_container_width=True)
    solar = view["solar_irradiance"]
    if solar:
        with st.expander("Solar irradiance data"):
            st.json(sanitized_result({"solar_irradiance": solar}), expanded=False)
    if view["input_temperature"] is not None:
        st.caption(f"Supplied reference temperature: {view['input_temperature']} °C · Elevation: {view['elevation'] if view['elevation'] is not None else 'not supplied'} m")


def display_result(body: dict):
    result = summarize_result_data(body)
    if not result:
        st.info("No completed result body is currently available. Check the activity status first.")
        return
    st.caption("Returned result fields: " + ", ".join(result.keys()))
    map_data = result.get("map_data")
    stats = result.get("stats_data")
    if isinstance(stats, dict):
        units = stats.get("units") or stats.get("Units")
        st.subheader("Heatmap statistics")
        if units:
            st.caption(f"Reported units: {units}")
        else:
            st.caption("Reported numeric values; verify units against the request's analytic type.")
        available_metrics(stats)
        dist = stats.get("Overall_temperature_distribution") or stats.get("overall_temperature_distribution")
        if isinstance(dist, list) and dist:
            vals = [float(x) for x in dist[:10000] if isinstance(x, (int, float))]
            if vals:
                df = pd.DataFrame({"Temperature": vals})
                st.plotly_chart(px.histogram(df, x="Temperature", nbins=24,
                         template="plotly_dark", title="Distribution of returned values"), use_container_width=True)
    if isinstance(map_data, dict):
        st.subheader("Heatmap geography")
        show_heatmap_points(map_data)
    segmentation = result.get("segmentation")
    if isinstance(segmentation, dict):
        st.subheader("Satellite segmentation")
        show_segments(segmentation.get("segments") or {})
        left, right = st.columns(2)
        with left:
            show_segmentation_image(result.get("original_image") or result.get("orignal_image"), "Original satellite image")
        with right:
            show_segmentation_image(segmentation.get("image_content"), "Segmentation mask")
    front = result.get("front") or result.get("Front")
    if isinstance(front, dict):
        st.subheader("Street View")
        show_segments(front.get("segments") or {})
        c1, c2 = st.columns(2)
        with c1:
            show_segmentation_image(front.get("original_image"), "Original street view")
        with c2:
            show_segmentation_image(front.get("segmented_image"), "Segmented street view")
    if isinstance(result.get("download_link"), str):
        st.success("Heat Intelligence PDF is ready; its temporary signed URL is not displayed or saved.")
        if st.button("Retrieve PDF now", type="secondary"):
            link = result["download_link"]
            if not link.startswith("https://"):
                st.error("Refusing to fetch a non-HTTPS download link")
            else:
                try:
                    pdf_response = requests.get(link, timeout=60, stream=True)
                    pdf_response.raise_for_status()
                    chunks = []
                    total = 0
                    for chunk in pdf_response.iter_content(65536):
                        total += len(chunk)
                        if total > 25 * 1024 * 1024:
                            raise ValueError("PDF exceeds 25 MB safety cap")
                        chunks.append(chunk)
                    pdf_bytes = b"".join(chunks)
                    if not pdf_bytes.startswith(b"%PDF"):
                        raise ValueError("Downloaded content is not a PDF")
                    st.session_state.pdf_data = pdf_bytes
                except (requests.RequestException, ValueError) as err:
                    st.error(f"PDF download failed: {err}")
        if st.session_state.get("pdf_data"):
            st.download_button("Download Heat Intelligence PDF", data=st.session_state.pdf_data,
                               file_name="fortyguard_heat_intelligence.pdf", mime="application/pdf")
    if isinstance(result.get("locations"), (dict, list)) or isinstance(result.get("parameters"), dict):
        show_environmental_results(result)
    with st.expander("Complete sanitized result structure"):
        st.json(sanitized_result({"result": result}), expanded=False)


with st.sidebar:
    st.markdown("### 🌡️ Test Lab")
    st.caption("Local, authenticated API evaluation")
    api_key = st.text_input("FortyGuard API key", type="password",
                            help="Held in this local session only. Never written to evidence files.")
    st.caption("Credentials remain in the local application session and are excluded from saved evidence. The local service must not be publicly exposed.")
    st.divider()
    st.markdown("**Testing controls**")
    st.success("Requests are manual only")
    st.caption("Premium prices shown are estimates from the documentation. Only successful completed tasks should consume credits.")
    st.divider()
    st.caption("Current credit balances are available in the official FortyGuard account dashboard.")
    st.markdown("[Official API documentation](https://docs-api.fortyguard.com/)")

st.markdown("""
<div class="hero"><div class="eyebrow">LOCAL API QUALITY WORKBENCH</div>
<h1>FortyGuard · Test Lab</h1>
<p>A structured environment for API validation, response analysis, data visualization, and reproducible evidence management.</p></div>
""", unsafe_allow_html=True)

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.markdown(f'<div class="kpi"><small>ANALYSIS ENDPOINTS</small><strong>{len(ENDPOINTS)} documented</strong></div>', unsafe_allow_html=True)
with col_b:
    st.markdown(f'<div class="kpi"><small>FULL SUITE · PREMIUM CREDITS</small><strong>{TOTAL_ESTIMATED_CREDITS:,}</strong></div>', unsafe_allow_html=True)
with col_c:
    st.markdown(f'<div class="kpi"><small>RECORDED LIVE CHECKS</small><strong>{len(evidence_records())}</strong></div>', unsafe_allow_html=True)

overview, history_tab, runner, results_tab, evidence_tab = st.tabs(["Overview", "Previous tests", "Run tests", "Results studio", "Evidence vault"])

with overview:
    st.subheader("Coverage plan")
    st.write("The tool supports every analysis POST endpoint supplied in the documentation, plus three focused error-handling checks and GET task status.")
    st.dataframe(pd.DataFrame([{"Service": v["title"], "Method": "POST", "Endpoint": v["path"],
                               "Premium credits / completion": v["credits"]} for v in ENDPOINTS.values()]),
                 hide_index=True, use_container_width=True)
    st.info("Prior manual evaluation results are recorded under **Previous tests** for reference and traceability. These results have not been re-executed within this application.")
    st.markdown("**Execution methodology:** Submit individual analysis requests, verify activity status, and review returned data. Batch submissions require explicit authorization because completed tasks consume API credits.")


with history_tab:
    st.subheader("Prior evaluation results")
    st.caption("Prior API and dashboard evaluation findings, documented from local terminal outputs and application screenshots. These historical results are presented for traceability and were not re-executed by this application.")
    history_file = Path(__file__).resolve().parent / "evidence" / "previous_tests.json"
    history_data = json.loads(history_file.read_text(encoding="utf-8"))
    past = history_data["tests"]
    api_past = [r for r in past if r["category"] == "API"]
    ui_past = [r for r in past if r["category"] == "Dashboard"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Previously recorded API checks", len(api_past))
    m2.metric("Dashboard observations", len(ui_past))
    m3.metric("Tests executed in this application", len(evidence_records()))
    choice = st.radio("View history", ["All", "API", "Dashboard"], horizontal=True)
    filtered = [r for r in past if choice == "All" or r["category"] == choice]
    st.dataframe(pd.DataFrame(filtered)[["category", "test", "outcome", "http", "detail"]],
                 use_container_width=True, hide_index=True)
    st.download_button("Export prior evaluation summary (CSV)",
                       pd.DataFrame(filtered).to_csv(index=False).encode("utf-8-sig"),
                       file_name="fortyguard_prior_tests.csv", mime="text/csv")
    st.markdown("**Recorded improvement opportunities**")
    st.markdown("- Standardize error envelopes (`message` vs `details.message`).\n"
                "- Improve first-run tutorial focus and onboarding modal positioning.\n"
                "- Make the measurement-unit behavior clearer, and check notification delivery separately.")
    with st.expander("Evaluation notes and supporting observations"):
        note_file = Path(__file__).resolve().parent / "evidence" / "prior_test_observations.md"
        st.markdown(note_file.read_text(encoding="utf-8"))


with runner:
    st.subheader("Submit an analysis")
    chosen = st.selectbox("Choose a documented API", options=list(ENDPOINTS),
                          format_func=lambda k: ENDPOINTS[k]["title"])
    endpoint = ENDPOINTS[chosen]
    st.caption(f'POST {endpoint["path"]} · Approx. {endpoint["credits"]:,} credits if completed · {endpoint["plan"]} access')
    st.caption("Request payloads may be modified to match the testing scenario. Example U.S. locations are not guaranteed to have complete data coverage.")
    with st.form("submit_form"):
        text_payload = st.text_area("Request JSON", value=json.dumps(default_payload(chosen), indent=2),
                                    height=310, key=f"payload_{chosen}")
        charge_ok = st.checkbox(f"Authorize one live API submission (estimated cost: {endpoint['credits']:,} credits upon completion)")
        do_submit = st.form_submit_button("Submit test request", type="primary", use_container_width=True)
    if do_submit:
        if not api_key:
            st.error("An API key is required. Configure authentication in the sidebar.")
        elif not charge_ok:
            st.warning("Explicit authorization for credit-consuming submissions is required.")
        else:
            try:
                payload = json.loads(text_payload)
                if not isinstance(payload, dict):
                    raise ValueError("Request JSON must be an object")
            except (ValueError, json.JSONDecodeError) as error:
                st.error(f"Invalid JSON: {error}")
            else:
                with st.spinner(f"Submitting {endpoint['title']} request..."):
                    code, body = submit(chosen, api_key, payload)
                remember(chosen, code, body, payload)
                saved = save_test(f"submit_{chosen}", "POST", endpoint["path"], payload,
                                  code, body, endpoint["credits"])
                show_outcome(code, body, st.session_state.last_test_name)
                if saved:
                    st.caption(f"Evidence saved: {saved.name}")

    st.divider()
    st.subheader("Check an activity")
    status_id = st.text_input("Activity ID", value=st.session_state.last_activity,
                              placeholder="Paste the activity_id from a submission", key=f"status_input_{st.session_state.last_activity}")
    c_one, c_two = st.columns([1, 2])
    with c_one:
        check_now = st.button("Check status now", use_container_width=True)
    with c_two:
        use_links = st.checkbox("Use lightweight result_delivery=links (heatmap only)")
    if check_now:
        if not api_key or not status_id.strip():
            st.error("Both an API key and an activity ID are required.")
        else:
            try:
                with st.spinner("Checking task status..."):
                    code, body = check_status(api_key, status_id, links=use_links)
                remember(st.session_state.last_endpoint or "status", code, body)
                saved = save_test("check_status", "GET", f"/v1/status/{status_id}",
                                  {"result_delivery": "links"} if use_links else None,
                                  code, body)
                show_outcome(code, body, st.session_state.last_test_name)
                if saved:
                    st.caption(f"Evidence saved: {saved.name}")
            except ValueError as exc:
                st.error(str(exc))

    st.divider()
    st.subheader("Non-billable error-path checks")
    st.caption("These intentionally invalid requests should be rejected before any paid task is created. Do not run them repeatedly.")
    negative = st.selectbox("Select test", ["Missing API key (401)", "Missing required payload (422)",
                                                 "Unknown activity ID (404)"])
    if st.button("Run selected negative test"):
        if negative == "Missing API key (401)":
            name, method, path, payload = "missing_key", "POST", "/v1/heatmap", {}
            code, body = api_call(method, path, payload=payload)
        elif not api_key:
            st.error("An API key is required for this test.")
            code, body = "skip", {}
        elif negative == "Missing required payload (422)":
            name, method, path, payload = "invalid_payload", "POST", "/v1/heatmap", {}
            code, body = api_call(method, path, api_key=api_key, payload=payload)
        else:
            name, method, path, payload = "invalid_activity", "GET", "/v1/status/00000000-0000-4000-8000-000000000000", None
            code, body = api_call(method, path, api_key=api_key)
        if code != "skip":
            remember(name, code, body, payload)
            saved = save_test(name, method, path, payload, code, body)
            show_outcome(code, body, st.session_state.last_test_name)
            if saved:
                st.caption(f"Evidence saved: {saved.name}")

    st.divider()
    with st.expander("Advanced · run ALL six analysis endpoints", expanded=False):
        st.warning(f"One request to every analysis service could consume ~{TOTAL_ESTIMATED_CREDITS:,} Premium credits if all complete. Some may fail due to geographic coverage or provider limitations.")
        batch_ack = st.checkbox("Authorize one live request to each of the six analysis endpoints")
        if st.button("Submit all six once", type="secondary", disabled=not (batch_ack and bool(api_key))):
            progress = st.progress(0)
            records = []
            for idx, (name, config) in enumerate(ENDPOINTS.items(), start=1):
                payload = default_payload(name)
                code, body = submit(name, api_key, payload)
                saved = save_test(f"batch_{name}", "POST", config["path"], payload,
                                  code, body, config["credits"], "Manual opt-in batch")
                records.append({"Service": config["title"], "HTTP": code,
                                "Activity ID": activity_id_from(body),
                                "Evidence": saved.name if saved else "Not saved"})
                if code and 200 <= code < 300:
                    remember(name, code, body, payload)
                progress.progress(idx / len(ENDPOINTS))
            st.dataframe(pd.DataFrame(records), hide_index=True, use_container_width=True)
            st.info("These are submission results only. Use Check an activity for final processing statuses; the batch does not automatically poll or resubmit.")

with results_tab:
    st.subheader("Response explorer")
    with st.expander("Open an existing local API response (no API call)"):
        st.caption("Load a completed status response JSON for visualization. Files are handled in the local session and are not copied to evidence storage. Do not upload files containing credentials or signed URLs.")
        import_file = st.file_uploader("Select response JSON", type=["json"], key="offline_response_json")
        if import_file is not None and st.button("Analyze this local response"):
            try:
                parsed = json.loads(import_file.getvalue())
                if not isinstance(parsed, dict) or not isinstance(parsed.get("data"), dict):
                    raise ValueError("Expected a status response containing a data object")
                remember("local_response", parsed.get("status_code"), parsed)
                st.success("Response loaded locally; no API request or credits used.")
            except (ValueError, json.JSONDecodeError) as exc:
                st.error(f"Response could not be loaded: {exc}")
    body = st.session_state.last_body
    if not isinstance(body, dict):
        st.info("Submit an analysis or check a completed activity in Run tests first. Results appear here without any extra API call.")
    else:
        st.caption(f"Latest request: {st.session_state.last_endpoint} · HTTP {st.session_state.last_http}")
        verdict, note = outcome_verdict(st.session_state.last_test_name, st.session_state.last_http, body)
        st.markdown(f"**Evaluation outcome:** {verdict} — {note}")
        state = activity_state(body)
        if state and state.lower() not in ("completed", "succeeded"):
            st.warning(f"Activity is {state}. Check its status again before examining results.")
        display_result(body)

with evidence_tab:
    st.subheader("Recorded evidence")
    records = evidence_records()
    st.caption("Only sanitized metadata and response summaries are written. No API keys, signed report URLs, large GeoJSON arrays, or base64 images.")
    if records:
        table = pd.DataFrame([{
            "Time (UTC)": r.get("recorded_at_utc"), "Test": r.get("test"),
            "HTTP": r.get("http_status"), "Task": r.get("task_status"),
            "Endpoint": r.get("endpoint"), "File": r.get("file")
        } for r in records])
        st.dataframe(table, use_container_width=True, hide_index=True)
        st.download_button("Download evidence index (CSV)", evidence_csv_bytes(),
                           file_name="fortyguard_test_index.csv", mime="text/csv")
        selected = st.selectbox("Inspect a saved evidence record", [r["file"] for r in records])
        chosen_entry = next(r for r in records if r["file"] == selected)
        st.json(chosen_entry, expanded=False)
        st.download_button("Download selected evidence (JSON)",
                           json.dumps({k: v for k, v in chosen_entry.items() if k != "file"}, indent=2),
                           file_name=selected, mime="application/json")
    else:
        st.info("No live tests have been executed through this application. Prior manual evaluation results are documented in evidence/prior_test_observations.md.")
    st.markdown("**Evidence submission:** Include a concise evaluation summary and selected screenshots. Exclude credentials, signed URLs, and unnecessarily large raw API responses.")
