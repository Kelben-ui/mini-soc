"""Whole-SOC summary report (Reports page "Generate report" button).

Builds a single styled HTML document in the **same format as the per-incident
report** (see ``routers/incidents.py::get_incident_report``), but covering the
whole environment: headline stats, the live threat level, severity/status
breakdowns, response-time metrics (MTTD/MTTC/MTTR), top offenders and the
incident list.

All values are read live from the database and every interpolated field is
escaped through :mod:`app.utils.report_html`, so it is safe against XSS just
like the incident report.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_role
from ..models.audit_log import AuditLog
from ..models.incident import Incident
from ..utils.report_html import esc, report_page
from .incidents import _serialize_incident
from .stats import get_stats


router = APIRouter(
    prefix="/api",
    tags=["Reports"],
)


def _fmt_seconds(value):
    """Render a seconds value as ``m s`` (or ``-`` when unavailable)."""
    if value is None:
        return "-"
    value = float(value)
    if value < 60:
        return f"{value:.1f}s"
    minutes, seconds = divmod(value, 60)
    return f"{int(minutes)}m {seconds:.0f}s"


def _dict_rows(mapping):
    if not mapping:
        return '<tr><td colspan="2" class="muted">No data.</td></tr>'
    return "".join(
        f"<tr><th>{esc(key)}</th><td>{esc(count)}</td></tr>"
        for key, count in sorted(mapping.items())
    )


@router.get("/reports/summary")
def get_summary_report(
    response: Response,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("analyst", "lead", "admin")),
):
    stats = get_stats(response=response, db=db, current_user=current_user)
    generated_at = datetime.now(timezone.utc)

    incidents = db.query(Incident).order_by(Incident.created_at.desc()).all()

    incident_rows = "".join(
        "<tr>"
        f"<td>{esc(row['incident_code'])}</td>"
        f"<td>{esc(row['title'])}</td>"
        f"<td>{esc(row['severity'])}</td>"
        f"<td>{esc(row['status'])}</td>"
        f"<td>{esc(row['category'])}</td>"
        f"<td>{esc(row['created_at'])}</td>"
        f"<td>{esc(_fmt_seconds(row['ttd_seconds']))}</td>"
        f"<td>{esc(_fmt_seconds(row['ttc_seconds']))}</td>"
        f"<td>{esc(_fmt_seconds(row['ttr_seconds']))}</td>"
        "</tr>"
        for row in (_serialize_incident(db, incident) for incident in incidents)
    ) or '<tr><td colspan="9" class="muted">No incidents recorded.</td></tr>'

    top_ips_rows = "".join(
        f"<tr><td>{esc(item['src_ip'])}</td><td>{esc(item['count'])}</td></tr>"
        for item in stats.get("top_source_ips", [])
    ) or '<tr><td colspan="2" class="muted">No data.</td></tr>'

    top_types_rows = "".join(
        f"<tr><td>{esc(item['type'])}</td><td>{esc(item['count'])}</td></tr>"
        for item in stats.get("top_attack_types", [])
    ) or '<tr><td colspan="2" class="muted">No data.</td></tr>'

    body = f"""
    <h1>Mini SOC Summary Report</h1>
    <p class="muted">Generated {esc(generated_at.isoformat())} UTC by
    {esc(getattr(current_user, 'username', 'unknown'))}.</p>

    <div class="section">
        <h2>Environment Overview</h2>
        <table>
            <tr><th>Threat level</th><td>{esc(stats.get('threat_level'))}</td></tr>
            <tr><th>Total events</th><td>{esc(stats.get('total_events', 0))}</td></tr>
            <tr><th>Total alerts</th><td>{esc(stats.get('total_alerts', 0))}</td></tr>
            <tr><th>Active alerts</th><td>{esc(stats.get('active_alerts', 0))}</td></tr>
            <tr><th>Total incidents</th><td>{esc(stats.get('total_incidents', 0))}</td></tr>
            <tr><th>Open incidents</th><td>{esc(stats.get('open_incidents', 0))}</td></tr>
            <tr><th>Agents online</th><td>{esc(stats.get('agents_online', 0))}</td></tr>
            <tr><th>IDS status</th><td>{esc(stats.get('ids_status'))}</td></tr>
        </table>
    </div>

    <div class="section">
        <h2>Mean Response Times</h2>
        <table>
            <tr><th>Mean time to detect (MTTD)</th>
                <td>{esc(_fmt_seconds(stats.get('mean_time_to_detect_seconds')))}</td></tr>
            <tr><th>Mean time to contain (MTTC)</th>
                <td>{esc(_fmt_seconds(stats.get('mean_time_to_contain_seconds')))}</td></tr>
            <tr><th>Mean time to resolve (MTTR)</th>
                <td>{esc(_fmt_seconds(stats.get('mean_time_to_resolve_seconds')))}</td></tr>
        </table>
    </div>

    <div class="section">
        <h2>Alerts by Severity</h2>
        <table>{_dict_rows(stats.get('alerts_by_severity'))}</table>
    </div>

    <div class="section">
        <h2>Incidents by Status</h2>
        <table>{_dict_rows(stats.get('incidents_by_status'))}</table>
    </div>

    <div class="section">
        <h2>Top Source IPs</h2>
        <table>
            <tr><th>Source IP</th><th>Alerts</th></tr>
            {top_ips_rows}
        </table>
    </div>

    <div class="section">
        <h2>Top Attack Types</h2>
        <table>
            <tr><th>Category</th><th>Alerts</th></tr>
            {top_types_rows}
        </table>
    </div>

    <div class="section">
        <h2>Incidents</h2>
        <table>
            <tr>
                <th>Code</th><th>Title</th><th>Severity</th><th>Status</th>
                <th>Category</th><th>Created</th>
                <th>TTD</th><th>TTC</th><th>TTR</th>
            </tr>
            {incident_rows}
        </table>
    </div>
    """

    audit = AuditLog(
        user_id=current_user.id,
        action="summary_report_viewed",
        resource_type="report",
        resource_id="summary",
        details="SOC summary report generated",
        created_at=generated_at,
    )

    db.add(audit)
    db.commit()

    return HTMLResponse(content=report_page("Mini SOC Summary Report", body))
