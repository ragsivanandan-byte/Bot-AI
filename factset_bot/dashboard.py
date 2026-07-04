"""Render the demo dashboard HTML — the visual centerpiece for the sales pitch."""
from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path

from .storage import CHANGE_TYPE_COMPANY, CHANGE_TYPE_ROLE, Change, User


@dataclass
class DashboardLinks:
    email_preview_href: str
    teams_preview_href: str
    teams_payload_href: str


def render_dashboard(users: list[User], changes: list[Change], links: DashboardLinks,
                     out_path: Path, generated_at: str) -> Path:
    changed_ids = {c.salesforce_id: c.change_type for c in changes}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        _template(users, changes, changed_ids, links, generated_at),
        encoding="utf-8",
    )
    return out_path


def _template(users, changes, changed_ids, links, generated_at) -> str:
    total_users = len(users)
    matched = sum(1 for u in users if u.linkedin_url)

    company_changes = [c for c in changes if c.change_type == CHANGE_TYPE_COMPANY]
    role_changes = [c for c in changes if c.change_type == CHANGE_TYPE_ROLE]
    transferable = sum(1 for c in company_changes if c.new_employer_is_client == 1)
    churn = sum(1 for c in company_changes if c.new_employer_is_client == 0)

    alerts_html = "".join(_alert_card(c) for c in changes) or """
        <div class="empty">No movement detected this week.</div>"""
    rows_html = "".join(_user_row(u, changed_ids.get(u.salesforce_id)) for u in users)

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FactSet Client Watch - Demo dashboard</title>
<style>
:root {{
  --bg:#f4f5f7; --card:#ffffff; --ink:#1a1f36; --muted:#697386;
  --border:#e3e8ee; --brand:#0f2645; --accent:#0a5cff;
  --danger:#b3261e; --danger-bg:#fdecea; --ok:#137333; --ok-bg:#e6f4ea;
  --info:#0b57d0; --info-bg:#e8f0fe;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;
       background:var(--bg); color:var(--ink); }}
header {{ background:var(--brand); color:#ffffff; padding:28px 32px; }}
header .brand {{ font-size:12px; letter-spacing:1.8px; text-transform:uppercase; opacity:.7; }}
header h1 {{ margin:6px 0 4px 0; font-size:26px; font-weight:600; }}
header .sub {{ font-size:14px; opacity:.8; }}
main {{ max-width:1160px; margin:0 auto; padding:24px 32px 60px 32px; }}
.kpis {{ display:grid; grid-template-columns:repeat(5,1fr); gap:14px; margin-bottom:28px; }}
.kpi {{ background:var(--card); border:1px solid var(--border); border-radius:12px;
        padding:18px 20px; }}
.kpi .label {{ font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:1px; }}
.kpi .value {{ font-size:30px; font-weight:600; margin-top:6px; }}
.kpi .split {{ font-size:12px; color:var(--muted); margin-top:6px; }}
.kpi.alert .value {{ color:var(--danger); }}
.kpi.info .value {{ color:var(--info); }}
.kpi.ok .value {{ color:var(--ok); }}
section.card {{ background:var(--card); border:1px solid var(--border); border-radius:12px;
                padding:20px 24px; margin-bottom:24px; }}
section.card h2 {{ margin:0 0 4px 0; font-size:17px; }}
section.card .hint {{ color:var(--muted); font-size:13px; margin-bottom:16px; }}
.alerts {{ display:grid; grid-template-columns:1fr; gap:14px; }}
.alert-item {{ border-radius:10px; overflow:hidden;
               display:grid; grid-template-columns:1fr auto; gap:16px; align-items:center;
               padding:16px 20px 16px 18px;
               border-left:8px solid #cbd5e1;
               background:#f8fafc; }}
.alert-item.outcome-transfer {{ background:#ecfdf3; border-left-color:#0d7f42; }}
.alert-item.outcome-churn    {{ background:#fef2f2; border-left-color:#c62828; }}
.alert-item.outcome-internal {{ background:#eff6ff; border-left-color:#1a56db; }}
.alert-item .header {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
.alert-item .name {{ font-weight:600; font-size:15.5px; }}
.alert-item .move {{ font-size:13.5px; margin-top:8px; color:#1e293b; }}
.alert-item .move strong {{ color:#0f172a; }}
.alert-item .title {{ font-size:12.5px; color:#475569; margin-top:5px; }}
.alert-item .account {{ font-size:11.5px; color:#475569; margin-top:5px;
                        font-family:'SF Mono','Cascadia Code','Roboto Mono',ui-monospace,monospace;
                        letter-spacing:-0.2px; }}
.tag {{ display:inline-block; padding:3px 9px; border-radius:999px; font-size:10.5px;
        font-weight:600; letter-spacing:.6px; text-transform:uppercase; }}
.tag.company {{ background:#fdecea; color:#b3261e; }}
.tag.role {{ background:#e8f0fe; color:#1a56db; }}
.outcome-badge {{ display:inline-flex; align-items:center; gap:6px;
                  padding:6px 12px 6px 10px; border-radius:999px;
                  font-size:11.5px; font-weight:700; letter-spacing:.5px;
                  text-transform:uppercase; color:#ffffff; }}
.outcome-badge.transfer {{ background:#0d7f42; }}
.outcome-badge.churn    {{ background:#c62828; }}
.outcome-badge.internal {{ background:#1a56db; }}
.outcome-badge svg {{ width:14px; height:14px; }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px;
          font-weight:500; }}
.badge.prev {{ background:var(--danger-bg); color:var(--danger); }}
.badge.next {{ background:var(--ok-bg); color:var(--ok); }}
.badge.rolefrom {{ background:#e6e9ef; color:#3c4257; }}
.badge.roleto {{ background:var(--info-bg); color:var(--info); }}
.arrow {{ margin:0 6px; color:var(--muted); }}
.linkbtn {{ background:var(--accent); color:#fff; padding:8px 12px; border-radius:6px;
            font-size:12px; text-decoration:none; white-space:nowrap; }}
.linkbtn.secondary {{ background:#ffffff; color:var(--accent); border:1px solid var(--accent); }}
.actions {{ display:flex; gap:10px; margin-top:12px; flex-wrap:wrap; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
thead th {{ text-align:left; font-size:11px; letter-spacing:1px; text-transform:uppercase;
            color:var(--muted); padding:10px 12px; border-bottom:1px solid var(--border); }}
tbody td {{ padding:12px; border-bottom:1px solid #f0f2f5; vertical-align:middle; }}
tr.company_change {{ background:#fff8f7; }}
tr.role_change {{ background:#f4f8ff; }}
tr.company_change td.status .status-badge {{ background:var(--danger-bg); color:var(--danger); }}
tr.role_change td.status .status-badge {{ background:var(--info-bg); color:var(--info); }}
td.status .status-badge {{ display:inline-block; padding:2px 8px; border-radius:999px;
                            font-size:11px; font-weight:500; background:var(--ok-bg); color:var(--ok); }}
.small {{ color:var(--muted); font-size:12px; }}
.li {{ font-size:12px; color:var(--accent); text-decoration:none; }}
.legend {{ font-size:12px; color:var(--muted); margin-top:12px; display:flex; gap:16px; flex-wrap:wrap; }}
.legend .dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; vertical-align:middle; }}
.legend .dot.company {{ background:var(--danger); }}
.legend .dot.role {{ background:var(--info); }}
.legend .dot.client {{ background:var(--ok); }}
.legend .dot.churn {{ background:var(--danger); }}
footer {{ text-align:center; color:var(--muted); font-size:12px; margin-top:20px; }}
.tag-demo {{ display:inline-block; background:#fff4d6; color:#8a5a00; padding:2px 8px;
             border-radius:999px; font-size:11px; margin-left:8px; vertical-align:middle; }}
@media (max-width: 900px) {{ .kpis {{ grid-template-columns:repeat(3,1fr); }} }}
@media (max-width: 600px) {{ .kpis {{ grid-template-columns:repeat(2,1fr); }} }}
</style>
</head>
<body>
  <header>
    <div class="brand">FactSet Client Watch <span class="tag-demo">Demo mode</span></div>
    <h1>Weekly alerts - user movements</h1>
    <div class="sub">Simulated run on {generated_at} &middot; portfolio of {total_users} FactSet users</div>
  </header>
  <main>
    <div class="kpis">
      <div class="kpi">
        <div class="label">Users monitored</div>
        <div class="value">{total_users}</div>
      </div>
      <div class="kpi ok">
        <div class="label">LinkedIn profiles resolved</div>
        <div class="value">{matched}</div>
        <div class="split">{matched}/{total_users}</div>
      </div>
      <div class="kpi alert">
        <div class="label">Employer changes</div>
        <div class="value">{len(company_changes)}</div>
      </div>
      <div class="kpi info">
        <div class="label">Internal mobility</div>
        <div class="value">{len(role_changes)}</div>
      </div>
      <div class="kpi">
        <div class="label">New employer FactSet client?</div>
        <div class="value" style="font-size:20px;line-height:1.6;">
          <span style="color:var(--ok);">{transferable}</span>&nbsp;transfer
          <span style="color:var(--muted);font-weight:400;font-size:14px;">/</span>
          <span style="color:var(--danger);">{churn}</span>&nbsp;churn
        </div>
        <div class="split">Based on Salesforce Account lookup</div>
      </div>
    </div>

    <section class="card">
      <h2>Active alerts</h2>
      <div class="hint">Each row is a movement detected on a LinkedIn profile since the last check. Employer changes and internal mobility are weighted equally.</div>
      <div class="alerts">{alerts_html}</div>
      <div class="legend">
        <span><span class="dot company"></span>Employer change</span>
        <span><span class="dot role"></span>Internal mobility</span>
        <span><span class="dot client"></span>New employer is a FactSet client (seat may transfer)</span>
        <span><span class="dot churn"></span>New employer is NOT a FactSet client (likely churn)</span>
      </div>
      <div class="actions">
        <a class="linkbtn" href="{html.escape(links.email_preview_href)}" target="_blank">View email digest</a>
        <a class="linkbtn secondary" href="{html.escape(links.teams_preview_href)}" target="_blank">View Teams card</a>
        <a class="linkbtn secondary" href="{html.escape(links.teams_payload_href)}" target="_blank">Teams JSON payload</a>
      </div>
    </section>

    <section class="card">
      <h2>FactSet portfolio</h2>
      <div class="hint">All {total_users} monitored users, with their current LinkedIn company &amp; title, and status for the week.</div>
      <table>
        <thead><tr>
          <th>Name</th><th>Salesforce company</th><th>LinkedIn company</th>
          <th>LinkedIn title</th><th>Profile</th><th class="status">Status</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </section>

    <footer>
      All data on this page is fictional, generated for demonstration purposes.
      In production, users come from Salesforce, LinkedIn signal comes from a compliant enrichment
      provider (Coresignal, People Data Labs, or LinkedIn's SNAP API), and the client-status of
      the new employer is verified against the Salesforce Account object.
    </footer>
  </main>
</body></html>"""


_SVG_CHECK = ('<svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" '
              'aria-hidden="true"><path d="M4 10.5l4 4L16 6" stroke="currentColor" '
              'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>')
_SVG_CROSS = ('<svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" '
              'aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" '
              'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>')
_SVG_ARROW = ('<svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" '
              'aria-hidden="true"><path d="M6 10h9m-3-3l3 3-3 3" stroke="currentColor" '
              'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def _outcome_class(c: Change) -> str:
    if c.change_type == CHANGE_TYPE_ROLE:
        return "outcome-internal"
    if c.new_employer_is_client:
        return "outcome-transfer"
    if c.new_employer_is_client == 0:
        return "outcome-churn"
    return ""


def _outcome_badge(c: Change) -> str:
    if c.change_type == CHANGE_TYPE_ROLE:
        return (f'<span class="outcome-badge internal">{_SVG_ARROW}'
                'Relationship opportunity</span>')
    if c.new_employer_is_client:
        return (f'<span class="outcome-badge transfer">{_SVG_CHECK}'
                'Seat may transfer</span>')
    if c.new_employer_is_client == 0:
        return (f'<span class="outcome-badge churn">{_SVG_CROSS}'
                'Likely churn</span>')
    return ""


def _alert_card(c: Change) -> str:
    if c.change_type == CHANGE_TYPE_ROLE:
        return _role_alert_card(c)
    return _company_alert_card(c)


def _company_alert_card(c: Change) -> str:
    name = html.escape(c.full_name)
    prev = html.escape(c.previous_company or "-")
    new = html.escape(c.new_company or "-")
    title = html.escape(c.new_title or "-")
    url = html.escape(c.linkedin_url or "#")
    outcome_cls = _outcome_class(c)
    badge = _outcome_badge(c)
    if c.new_employer_is_client:
        client_line = (
            f'<div class="account">Salesforce account: {html.escape(c.new_employer_account_id or "-")} '
            f'&middot; {new} is an existing FactSet client</div>'
        )
    elif c.new_employer_is_client == 0:
        client_line = (
            f'<div class="account">{new} is NOT on the FactSet client roster &mdash; '
            'seat likely lost</div>'
        )
    else:
        client_line = ""
    return f"""
      <div class="alert-item {outcome_cls}">
        <div>
          <div class="header">
            <span class="tag company">Employer change</span>
            <span class="name">{name}</span>
            {badge}
          </div>
          <div class="move">{prev} &rarr; <strong>{new}</strong></div>
          <div class="title">New title:&nbsp;{title}</div>
          {client_line}
        </div>
        <a class="linkbtn" href="{url}" target="_blank">Open LinkedIn</a>
      </div>"""


def _role_alert_card(c: Change) -> str:
    name = html.escape(c.full_name)
    company = html.escape(c.new_company or "-")
    prev_title = html.escape(c.previous_title or "-")
    new_title = html.escape(c.new_title or "-")
    url = html.escape(c.linkedin_url or "#")
    return f"""
      <div class="alert-item outcome-internal">
        <div>
          <div class="header">
            <span class="tag role">Internal mobility</span>
            <span class="name">{name}</span>
            {_outcome_badge(c)}
          </div>
          <div class="move">{prev_title} &rarr; <strong>{new_title}</strong></div>
          <div class="title">Still at:&nbsp;{company}</div>
        </div>
        <a class="linkbtn" href="{url}" target="_blank">Open LinkedIn</a>
      </div>"""


def _user_row(u: User, change_type: str | None) -> str:
    name = html.escape(u.full_name)
    sf_company = html.escape(u.salesforce_company)
    li_company = html.escape(u.current_company or "-")
    li_title = html.escape(u.current_title or "-")
    li_url = html.escape(u.linkedin_url or "")
    profile_cell = (
        f'<a class="li" href="{li_url}" target="_blank">linkedin.com/in/...</a>'
        if li_url else '<span class="small">Not resolved</span>'
    )
    if change_type == CHANGE_TYPE_COMPANY:
        cls = "company_change"
        status = "Changed employer"
    elif change_type == CHANGE_TYPE_ROLE:
        cls = "role_change"
        status = "Internal mobility"
    else:
        cls = ""
        status = "Stable"
    return f"""
        <tr class="{cls}">
          <td><strong>{name}</strong></td>
          <td>{sf_company}</td>
          <td>{li_company}</td>
          <td>{li_title}</td>
          <td>{profile_cell}</td>
          <td class="status"><span class="status-badge">{status}</span></td>
        </tr>"""
