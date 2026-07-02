"""Render the demo dashboard HTML — the visual centerpiece for the sales pitch."""
from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path

from .storage import Change, User


@dataclass
class DashboardLinks:
    email_preview_href: str
    teams_preview_href: str
    teams_payload_href: str


def render_dashboard(users: list[User], changes: list[Change], links: DashboardLinks,
                     out_path: Path, generated_at: str) -> Path:
    changed_ids = {c.salesforce_id for c in changes}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        _template(users, changes, changed_ids, links, generated_at),
        encoding="utf-8",
    )
    return out_path


def _template(users, changes, changed_ids, links, generated_at) -> str:
    kpi_total = len(users)
    kpi_matched = sum(1 for u in users if u.linkedin_url)
    kpi_alerts = len(changes)
    alerts_html = "".join(_alert_card(c) for c in changes) or """
        <div class="empty">Aucun changement d'employeur d&eacute;tect&eacute; cette semaine.</div>"""
    rows_html = "".join(_user_row(u, u.salesforce_id in changed_ids) for u in users)

    return f"""<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FactSet Client Watch - Dashboard d&eacute;mo</title>
<style>
:root {{
  --bg:#f4f5f7; --card:#ffffff; --ink:#1a1f36; --muted:#697386;
  --border:#e3e8ee; --brand:#0f2645; --accent:#0a5cff;
  --danger:#b3261e; --danger-bg:#fdecea; --ok:#137333; --ok-bg:#e6f4ea;
  --warn:#8a5a00; --warn-bg:#fff4d6;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;
       background:var(--bg); color:var(--ink); }}
header {{ background:var(--brand); color:#ffffff; padding:28px 32px; }}
header .brand {{ font-size:12px; letter-spacing:1.8px; text-transform:uppercase; opacity:.7; }}
header h1 {{ margin:6px 0 4px 0; font-size:26px; font-weight:600; }}
header .sub {{ font-size:14px; opacity:.8; }}
main {{ max-width:1160px; margin:0 auto; padding:24px 32px 60px 32px; }}
.kpis {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin-bottom:28px; }}
.kpi {{ background:var(--card); border:1px solid var(--border); border-radius:12px;
        padding:18px 20px; }}
.kpi .label {{ font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:1px; }}
.kpi .value {{ font-size:32px; font-weight:600; margin-top:6px; }}
.kpi.alert .value {{ color:var(--danger); }}
.kpi.ok .value {{ color:var(--ok); }}
section.card {{ background:var(--card); border:1px solid var(--border); border-radius:12px;
                padding:20px 24px; margin-bottom:24px; }}
section.card h2 {{ margin:0 0 4px 0; font-size:17px; }}
section.card .hint {{ color:var(--muted); font-size:13px; margin-bottom:16px; }}
.alerts {{ display:grid; grid-template-columns:1fr; gap:14px; }}
.alert-item {{ border:1px solid #f3c3bf; background:#fff8f7; border-radius:10px;
               padding:14px 16px; display:grid; grid-template-columns:1fr auto; gap:14px; align-items:center; }}
.alert-item .name {{ font-weight:600; font-size:15px; }}
.alert-item .move {{ font-size:13px; margin-top:6px; }}
.alert-item .title {{ font-size:12px; color:var(--muted); margin-top:4px; }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px;
          font-weight:500; }}
.badge.prev {{ background:var(--danger-bg); color:var(--danger); }}
.badge.next {{ background:var(--ok-bg); color:var(--ok); }}
.arrow {{ margin:0 6px; color:var(--muted); }}
.linkbtn {{ background:var(--accent); color:#fff; padding:8px 12px; border-radius:6px;
            font-size:12px; text-decoration:none; white-space:nowrap; }}
.linkbtn.secondary {{ background:#ffffff; color:var(--accent); border:1px solid var(--accent); }}
.actions {{ display:flex; gap:10px; margin-top:8px; flex-wrap:wrap; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
thead th {{ text-align:left; font-size:11px; letter-spacing:1px; text-transform:uppercase;
            color:var(--muted); padding:10px 12px; border-bottom:1px solid var(--border); }}
tbody td {{ padding:12px; border-bottom:1px solid #f0f2f5; vertical-align:middle; }}
tr.changed {{ background:#fff8f7; }}
tr.changed td.status .badge {{ background:var(--danger-bg); color:var(--danger); }}
td.status .badge {{ background:var(--ok-bg); color:var(--ok); }}
.small {{ color:var(--muted); font-size:12px; }}
.li {{ font-size:12px; color:var(--accent); text-decoration:none; }}
footer {{ text-align:center; color:var(--muted); font-size:12px; margin-top:20px; }}
.tag-demo {{ display:inline-block; background:#fff4d6; color:#8a5a00; padding:2px 8px;
             border-radius:999px; font-size:11px; margin-left:8px; vertical-align:middle; }}
</style>
</head>
<body>
  <header>
    <div class="brand">FactSet Client Watch <span class="tag-demo">Mode d&eacute;monstration</span></div>
    <h1>Alertes hebdomadaires - changements d'employeur</h1>
    <div class="sub">Ex&eacute;cution simul&eacute;e du {generated_at} &middot; portefeuille de {kpi_total} utilisateurs FactSet</div>
  </header>
  <main>
    <div class="kpis">
      <div class="kpi"><div class="label">Utilisateurs monitor&eacute;s</div><div class="value">{kpi_total}</div></div>
      <div class="kpi ok"><div class="label">Profils LinkedIn r&eacute;solus</div><div class="value">{kpi_matched}</div></div>
      <div class="kpi alert"><div class="label">Alertes cette semaine</div><div class="value">{kpi_alerts}</div></div>
    </div>

    <section class="card">
      <h2>Alertes actives</h2>
      <div class="hint">Chaque utilisateur ci-dessous a une nouvelle soci&eacute;t&eacute; sur son profil LinkedIn depuis la derni&egrave;re v&eacute;rification.</div>
      <div class="alerts">{alerts_html}</div>
      <div class="actions">
        <a class="linkbtn" href="{html.escape(links.email_preview_href)}" target="_blank">Voir l'email envoy&eacute;</a>
        <a class="linkbtn secondary" href="{html.escape(links.teams_preview_href)}" target="_blank">Voir la carte Teams</a>
        <a class="linkbtn secondary" href="{html.escape(links.teams_payload_href)}" target="_blank">Payload JSON Teams</a>
      </div>
    </section>

    <section class="card">
      <h2>Portefeuille FactSet</h2>
      <div class="hint">Les {kpi_total} utilisateurs suivis, avec leur soci&eacute;t&eacute; LinkedIn actuelle et leur statut.</div>
      <table>
        <thead><tr>
          <th>Nom</th><th>Soci&eacute;t&eacute; Salesforce</th><th>Soci&eacute;t&eacute; LinkedIn actuelle</th>
          <th>Poste LinkedIn</th><th>Profil</th><th class="status">Statut</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </section>

    <footer>
      Toutes les donn&eacute;es de cette page sont fictives, g&eacute;n&eacute;r&eacute;es pour la d&eacute;monstration.
      En production, les utilisateurs proviennent de Salesforce et les profils sont interrog&eacute;s via l'API LinkedIn (Proxycurl).
    </footer>
  </main>
</body></html>"""


def _alert_card(c: Change) -> str:
    name = html.escape(c.full_name)
    prev = html.escape(c.previous_company or "-")
    new = html.escape(c.new_company or "-")
    title = html.escape(c.new_title or "-")
    url = html.escape(c.linkedin_url or "#")
    return f"""
      <div class="alert-item">
        <div>
          <div class="name">{name}</div>
          <div class="move">
            <span class="badge prev">Ancien</span>&nbsp;{prev}
            <span class="arrow">&rarr;</span>
            <span class="badge next">Nouveau</span>&nbsp;<strong>{new}</strong>
          </div>
          <div class="title">Nouveau poste&nbsp;: {title}</div>
        </div>
        <div><a class="linkbtn" href="{url}" target="_blank">Ouvrir LinkedIn</a></div>
      </div>"""


def _user_row(u: User, is_changed: bool) -> str:
    name = html.escape(u.full_name)
    sf_company = html.escape(u.salesforce_company)
    li_company = html.escape(u.current_company or "-")
    li_title = html.escape(u.current_title or "-")
    li_url = html.escape(u.linkedin_url or "")
    status = ("Chang&eacute; cette semaine" if is_changed else "Stable")
    profile_cell = (
        f'<a class="li" href="{li_url}" target="_blank">linkedin.com/in/...</a>'
        if li_url else '<span class="small">Non r&eacute;solu</span>'
    )
    cls = "changed" if is_changed else ""
    return f"""
        <tr class="{cls}">
          <td><strong>{name}</strong></td>
          <td>{sf_company}</td>
          <td>{li_company}</td>
          <td>{li_title}</td>
          <td>{profile_cell}</td>
          <td class="status"><span class="badge">{status}</span></td>
        </tr>"""
