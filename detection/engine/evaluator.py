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

        # A rule's ``regex`` list is a set of alternatives: any one match is
        # enough, mirroring how ``contains`` is evaluated (``any``).  Requiring
        # *every* pattern previously made multi-pattern rules such as
        # WEB-BF-001 (DVWA's /login.php *or* /brute) impossible to satisfy.
        if not any(_regex_search(pat, search_text) for pat in regex_patterns):
            return False

    return True


def _regex_search(pattern, text):
    """Return True if ``pattern`` matches ``text``.

    Falls back to a literal substring test when the configured pattern is not a
    valid regular expression, so a typo in a rule degrades to a ``contains``
    check instead of silently disabling the whole rule.
    """
    import re

    try:
        return bool(re.search(pattern, text, re.IGNORECASE))
    except Exception:
        return str(pattern).lower() in text


def get_threshold_events(events, rule):
    threshold = rule.get("threshold")

    if not threshold:
        return events

    required_count = threshold["count"]
    window_seconds = threshold["window_seconds"]
    group_by = threshold.get("group_by", []) or []

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

    if not group_by:
        latest_event = matching_events[-1]
        latest_time = get_event_value(latest_event, "timestamp")
        window_start = latest_time - timedelta(seconds=window_seconds)
        window_events = [
            event
            for event in matching_events
            if window_start <= get_event_value(event, "timestamp") <= latest_time
        ]
        if len(window_events) >= required_count:
            return window_events
        return []

    triggered_events = []
    for group_key, group_events in _group_events(matching_events, group_by).items():
        group_events_sorted = sorted(group_events, key=lambda event: get_event_value(event, "timestamp"))
        if not group_events_sorted:
            continue
        latest_event = group_events_sorted[-1]
        latest_time = get_event_value(latest_event, "timestamp")
        window_start = latest_time - timedelta(seconds=window_seconds)
        window_events = [
            event
            for event in group_events_sorted
            if window_start <= get_event_value(event, "timestamp") <= latest_time
        ]
        if len(window_events) >= required_count:
            triggered_events.extend(window_events)
    return triggered_events


def _group_events(events, group_by):
    grouped = {}
    for event in events:
        key = tuple(_get_nested_value(event, field) if '.' in field else get_event_value(event, field) for field in group_by)
        if all(v is not None for v in key):
            grouped.setdefault(key, []).append(event)
    return grouped
