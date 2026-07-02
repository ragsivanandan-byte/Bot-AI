"""End-to-end demo orchestrator: runs the full pipeline against fake data with live console output."""
from __future__ import annotations

import sys
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from . import alerts as alerts_module
from . import matcher, monitor
from .dashboard import DashboardLinks, render_dashboard
from .mock_client import MockProxycurlClient
from .salesforce_ingest import load_csv
from .storage import CHANGE_TYPE_COMPANY, CHANGE_TYPE_ROLE, Storage


def run_demo(csv_path: Path, out_dir: Path, open_browser: bool = True,
             pause: float = 0.6) -> Path:
    """Run the whole pipeline against fake data and return the dashboard path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    db_path = out_dir / "demo_state.db"
    if db_path.exists():
        db_path.unlink()  # fresh run every demo
    storage = Storage(db_path)
    client = MockProxycurlClient()

    _step("1/5", "Ingestion des utilisateurs FactSet depuis l'export Salesforce")
    seen, ingested = load_csv(csv_path, storage)
    print(f"      -> {seen} lignes lues, {ingested} utilisateurs ingeres.")
    time.sleep(pause)

    _step("2/5", "Rapprochement des noms + societes avec les profils LinkedIn")
    attempted, matched = matcher.match_all_unresolved(storage, client)
    print(f"      -> {matched}/{attempted} profils LinkedIn resolus (mock Proxycurl).")
    time.sleep(pause)

    _step("3/5", "Simulation d'une semaine ecoulee (le mock avance dans le temps)")
    client.advance_week()
    print("      -> Semaine +1. Les profils LinkedIn sont a nouveau interroges...")
    time.sleep(pause)

    _step("4/5", "Detection des mouvements RH (changement de societe et mobilite interne)")
    checked, company_changes, role_changes = monitor.check_all(storage, client)
    print(f"      -> {checked} profils verifies, {company_changes} changement(s) de societe, "
          f"{role_changes} mobilite(s) interne(s).")
    time.sleep(pause)

    _step("5/5", "Generation des alertes (email + Teams) et du dashboard")
    pending = storage.get_pending_changes()
    alerts_out = alerts_module.render_demo_alerts(pending, out_dir)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    dashboard_path = out_dir / "dashboard.html"
    links = DashboardLinks(
        email_preview_href=alerts_out.email_html_path.name,
        teams_preview_href=alerts_out.teams_preview_html_path.name,
        teams_payload_href=alerts_out.teams_payload_path.name,
    )
    users = storage.get_all_users()
    render_dashboard(users, pending, links, dashboard_path, generated_at)

    ids = storage.get_pending_change_ids()
    storage.mark_changes_notified(ids)
    print(f"      -> Dashboard: {dashboard_path}")
    print(f"      -> Email preview: {alerts_out.email_html_path}")
    print(f"      -> Teams preview: {alerts_out.teams_preview_html_path}")

    print()
    _banner("DEMO TERMINEE", pending, users)

    if open_browser:
        try:
            webbrowser.open(dashboard_path.resolve().as_uri())
        except Exception:
            pass

    return dashboard_path


def _step(tag: str, msg: str) -> None:
    print(f"[{tag}] {msg}")


def _banner(title: str, changes, users) -> None:
    company = [c for c in changes if c.change_type == CHANGE_TYPE_COMPANY]
    role = [c for c in changes if c.change_type == CHANGE_TYPE_ROLE]
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)
    print(f"  Utilisateurs FactSet suivis    : {len(users)}")
    print(f"  Changements de societe         : {len(company)}")
    for c in company:
        print(f"    * {c.full_name}: {c.previous_company} -> {c.new_company}")
    print(f"  Mobilites internes             : {len(role)}")
    for c in role:
        print(f"    * {c.full_name} @ {c.new_company}: {c.previous_title} -> {c.new_title}")
    print("=" * 72)
    print()
    print("Ouvre dashboard.html dans un navigateur pour la vue manager.")
    sys.stdout.flush()
