from collections import defaultdict
from flask import Flask, Response, jsonify, request
import os
from time import monotonic, time
from threading import Lock

app = Flask(__name__)

METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
APP_START_TIME = time()
LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
SEVERITY_LEVELS = ("critical", "high", "medium", "low")

REQUEST_COUNTS = defaultdict(int)
REQUEST_STATUS_COUNTS = defaultdict(int)
REQUEST_LATENCY_SUM = defaultdict(float)
REQUEST_LATENCY_COUNT = defaultdict(int)
REQUEST_LATENCY_BUCKET_COUNTS = defaultdict(int)
ERROR_COUNTS = defaultdict(int)
DOMAIN_EVENT_COUNTS = defaultdict(int)
IN_FLIGHT_REQUESTS = 0
METRICS_LOCK = Lock()


def _escape_label(value):
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _observe_request_latency(method, endpoint, status_code, duration_seconds):
    key = (method, endpoint, status_code)
    REQUEST_LATENCY_SUM[key] += duration_seconds
    REQUEST_LATENCY_COUNT[key] += 1

    for bucket in LATENCY_BUCKETS:
        if duration_seconds <= bucket:
            REQUEST_LATENCY_BUCKET_COUNTS[(method, endpoint, status_code, bucket)] += 1

    REQUEST_LATENCY_BUCKET_COUNTS[(method, endpoint, status_code, "+Inf")] += 1


def _bucket_sort_value(bucket):
    if bucket == "+Inf":
        return float("inf")
    return float(bucket)

@app.get("/")
def home():
    with METRICS_LOCK:
        DOMAIN_EVENT_COUNTS[("page_view", "home")] += 1
    return jsonify(
        {
            "name": "sevflow-app",
            "status": "ok",
            "message": "Welcome to the Sevflow microservice -15",
            "version": os.getenv("APP_VERSION", "1.0.0"),
            "environment": os.getenv("APP_ENV", "dev"),
        }
    )


@app.get("/health")
def health():
    return jsonify({"status": "healthy"}), 200


@app.get("/api/severity")
def severity():
    with METRICS_LOCK:
        DOMAIN_EVENT_COUNTS[("api_call", "severity")] += 1
        for level in SEVERITY_LEVELS:
            DOMAIN_EVENT_COUNTS[("severity_level_exposed", level)] += 1
    return jsonify(
        {
            "service": "sevflow-app",
            "severityLevels": ["critical", "high", "medium", "low"],
        }
    )


@app.before_request
def before_request():
    global IN_FLIGHT_REQUESTS

    request.environ["request_start_time"] = monotonic()
    with METRICS_LOCK:
        IN_FLIGHT_REQUESTS += 1


@app.after_request
def record_request(response):
    global IN_FLIGHT_REQUESTS

    endpoint = request.url_rule.rule if request.url_rule else request.path
    start_time = request.environ.get("request_start_time", monotonic())
    duration_seconds = max(monotonic() - start_time, 0.0)
    status_code = response.status_code

    with METRICS_LOCK:
        REQUEST_COUNTS[(request.method, endpoint)] += 1
        REQUEST_STATUS_COUNTS[(request.method, endpoint, status_code)] += 1
        _observe_request_latency(request.method, endpoint, status_code, duration_seconds)
        IN_FLIGHT_REQUESTS = max(IN_FLIGHT_REQUESTS - 1, 0)
    return response


@app.errorhandler(Exception)
def handle_exception(error):
    endpoint = request.url_rule.rule if request.url_rule else request.path

    with METRICS_LOCK:
        ERROR_COUNTS[(type(error).__name__, endpoint)] += 1

    raise error


@app.get("/metrics")
def metrics():
    app_version = os.getenv("APP_VERSION", "1.0.0")
    app_env = os.getenv("APP_ENV", "dev")
    git_commit = os.getenv("GIT_COMMIT", "unknown")
    pod_name = os.getenv("HOSTNAME", "unknown")
    python_version = os.getenv("PYTHON_VERSION", "3.x")

    with METRICS_LOCK:
        request_counts = list(REQUEST_COUNTS.items())
        request_status_counts = list(REQUEST_STATUS_COUNTS.items())
        request_latency_sum = list(REQUEST_LATENCY_SUM.items())
        request_latency_count = list(REQUEST_LATENCY_COUNT.items())
        request_latency_buckets = list(REQUEST_LATENCY_BUCKET_COUNTS.items())
        error_counts = list(ERROR_COUNTS.items())
        domain_event_counts = list(DOMAIN_EVENT_COUNTS.items())
        in_flight_requests = IN_FLIGHT_REQUESTS

    lines = [
        "# HELP sevflow_app_info Static metadata about the Sevflow app.",
        "# TYPE sevflow_app_info gauge",
        (
            f'sevflow_app_info{{version="{_escape_label(app_version)}",'
            f'environment="{_escape_label(app_env)}",commit="{_escape_label(git_commit)}",'
            f'pod="{_escape_label(pod_name)}",python_version="{_escape_label(python_version)}"}} 1'
        ),
        "# HELP sevflow_health_status Health status for the Sevflow app.",
        "# TYPE sevflow_health_status gauge",
        "sevflow_health_status 1",
        "# HELP sevflow_process_start_time_seconds Unix time when the Sevflow app started.",
        "# TYPE sevflow_process_start_time_seconds gauge",
        f"sevflow_process_start_time_seconds {APP_START_TIME}",
        "# HELP sevflow_process_uptime_seconds Seconds since the Sevflow app started.",
        "# TYPE sevflow_process_uptime_seconds gauge",
        f"sevflow_process_uptime_seconds {max(time() - APP_START_TIME, 0.0)}",
        "# HELP sevflow_http_requests_total Total HTTP requests handled by the Sevflow app.",
        "# TYPE sevflow_http_requests_total counter",
        "# HELP sevflow_http_requests_by_status_total Total HTTP requests by status code.",
        "# TYPE sevflow_http_requests_by_status_total counter",
        "# HELP sevflow_http_request_duration_seconds Request latency in seconds.",
        "# TYPE sevflow_http_request_duration_seconds histogram",
        "# HELP sevflow_http_in_flight_requests Current number of in-flight requests.",
        "# TYPE sevflow_http_in_flight_requests gauge",
        f"sevflow_http_in_flight_requests {in_flight_requests}",
        "# HELP sevflow_app_errors_total Total unhandled application errors.",
        "# TYPE sevflow_app_errors_total counter",
        "# HELP sevflow_domain_events_total Total Sevflow domain events.",
        "# TYPE sevflow_domain_events_total counter",
    ]

    for (method, endpoint), count in sorted(request_counts):
        lines.append(
            f'sevflow_http_requests_total{{method="{_escape_label(method)}",endpoint="{_escape_label(endpoint)}"}} {count}'
        )

    for (method, endpoint, status_code), count in sorted(request_status_counts):
        lines.append(
            "sevflow_http_requests_by_status_total"
            f'{{method="{_escape_label(method)}",endpoint="{_escape_label(endpoint)}",status="{status_code}"}} {count}'
        )

    for (method, endpoint, status_code, bucket), count in sorted(
        request_latency_buckets,
        key=lambda item: (
            item[0][0],
            item[0][1],
            item[0][2],
            _bucket_sort_value(item[0][3]),
        ),
    ):
        bucket_value = bucket if bucket == "+Inf" else f"{bucket:g}"
        lines.append(
            "sevflow_http_request_duration_seconds_bucket"
            f'{{method="{_escape_label(method)}",endpoint="{_escape_label(endpoint)}",status="{status_code}",le="{bucket_value}"}} {count}'
        )

    for (method, endpoint, status_code), count in sorted(request_latency_count):
        lines.append(
            "sevflow_http_request_duration_seconds_count"
            f'{{method="{_escape_label(method)}",endpoint="{_escape_label(endpoint)}",status="{status_code}"}} {count}'
        )

    for (method, endpoint, status_code), duration_sum in sorted(request_latency_sum):
        lines.append(
            "sevflow_http_request_duration_seconds_sum"
            f'{{method="{_escape_label(method)}",endpoint="{_escape_label(endpoint)}",status="{status_code}"}} {duration_sum}'
        )

    for (error_type, endpoint), count in sorted(error_counts):
        lines.append(
            "sevflow_app_errors_total"
            f'{{error_type="{_escape_label(error_type)}",endpoint="{_escape_label(endpoint)}"}} {count}'
        )

    for (event_type, event_name), count in sorted(domain_event_counts):
        lines.append(
            "sevflow_domain_events_total"
            f'{{event_type="{_escape_label(event_type)}",event_name="{_escape_label(event_name)}"}} {count}'
        )

    body = "\n".join(lines) + "\n"
    return Response(body, mimetype=METRICS_CONTENT_TYPE)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
