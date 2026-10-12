from datetime import timedelta


def get_event_value(event, field):
    if isinstance(event, dict):
        return event.get(field)

    return getattr(event, field, None)


def get_detail_value(event, field):
    details = get_event_value(event, "details")

    if not isinstance(details, dict):
        return None

    return details.get(field)


def get_search_text(event):
    details = get_event_value(event, "details")
    raw = get_event_value(event, "raw")

    parts = []

    if details:
        parts.append(str(details))

    if raw:
        parts.append(str(raw))

    return " ".join(parts).lower()


def _get_nested_value(obj, path):
    if not path:
        return obj
    current = obj
    for part in str(path).split('.'):
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        else:
            current = getattr(current, part, None)
            if current is None:
                return None
    return current


def matches_rule(event, rule):
    conditions = rule.get("match", {})

    for field, expected_value in conditions.items():

        # Normal standardized event fields
        if field != "details":
            actual_value = _get_nested_value(event, field)

            if actual_value != expected_value:
                return False

    # Match fields inside standardized event details
    detail_conditions = conditions.get("details", {})

    for field, expected_value in detail_conditions.items():
        actual_value = _get_nested_value(event, f"details.{field}") if '.' not in field else _get_nested_value(event, field)  # handle nested

        # also try direct
        if actual_value is None and '.' not in field:
            actual_value = get_detail_value(event, field)

        if actual_value != expected_value:
            return False

    patterns = rule.get("contains", [])
    regex_patterns = rule.get("regex", [])

    search_text = get_search_text(event) if (patterns or regex_patterns) else ""

    if patterns:
        if not any(str(pattern).lower() in search_text for pattern in patterns):
            return False

    if regex_patterns:
        import re
        for pat in regex_patterns:
            try:
                if not re.search(pat, search_text, re.IGNORECASE):
                    return False
            except Exception:
                if str(pat).lower() not in search_text:
                    return False

    return True


def get_threshold_events(events, rule):
    threshold = rule.get("threshold")

    if not threshold:
        return events

    required_count = threshold["count"]
    window_seconds = threshold["window_seconds"]
    group_by = threshold.get("group_by", [])

    matching_events = [
        event
        for event in events
        if matches_rule(event, rule)
    ]

    if not matching_events:
        return []

    matching_events.sort(
        key=lambda event: get_event_value(event, "timestamp")
    )

    latest_event = matching_events[-1]

    latest_time = get_event_value(
        latest_event,
        "timestamp"
    )

    window_start = latest_time - timedelta(
        seconds=window_seconds
    )

    window_events = [
        event
        for event in matching_events
        if window_start
        <= get_event_value(event, "timestamp")
        <= latest_time
    ]

    if group_by:
        window_events = [
            event
            for event in window_events
            if tuple(
                _get_nested_value(event, field) if '.' in field else get_event_value(event, field)
                for field in group_by
            )
        ]  # threshold over groups present in window (per-group evaluation by caller)

    if len(window_events) >= required_count:
        return window_events

    return []
