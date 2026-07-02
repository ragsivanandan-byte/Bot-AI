"""Alert rendering. Demo mode writes HTML previews; production mode sends via SMTP/Teams webhook."""
from __future__ import annotations

import html
import json
import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Iterable

from .storage import CHANGE_TYPE_COMPANY, CHANGE_TYPE_ROLE, Change


@dataclass
class AlertOutputs:
    email_html_path: Path
    teams_preview_html_path: Path
    teams_payload_path: Path


def render_demo_alerts(changes: Iterable[Change], out_dir: Path) -> AlertOutputs:
    """Write email + Teams previews to `out_dir` and return their paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    change_list = list(changes)

    email_html = _render_email_html(change_list)
    email_path = out_dir / "alert_email_preview.html"
    email_path.write_text(email_html, encoding="utf-8")

    teams_card = _render_teams_card(change_list)
    teams_payload_path = out_dir / "alert_teams_payload.json"
    teams_payload_path.write_text(json.dumps(teams_card, indent=2), encoding="utf-8")

    teams_html = _render_teams_preview_html(change_list)
    teams_preview_path = out_dir / "alert_teams_preview.html"
    teams_preview_path.write_text(teams_html, encoding="utf-8")

    return AlertOutputs(
        email_html_path=email_path,
        teams_preview_html_path=teams_preview_path,
        teams_payload_path=teams_payload_path,
    )


def send_email(email_html: str, subject: str, smtp_host: str, smtp_port: int,
               smtp_user: str, smtp_password: str, sender: str,
               recipients: list[str], use_tls: bool = True) -> None:
    """Send the digest email in production mode."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(email_html, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        if use_tls:
            server.starttls()
        if smtp_user:
            server.login(smtp_user, smtp_password)
        server.sendmail(sender, recipients, msg.as_string())


def send_teams(webhook_url: str, payload: dict) -> None:
    """Post the Teams Adaptive Card in production mode."""
    import requests  # lazy so demo mode does not need requests installed
    resp = requests.post(webhook_url, json=payload, timeout=15)
    resp.raise_for_status()


def _render_email_html(changes: list[Change]) -> str:
    company_changes = [c for c in changes if c.change_type == CHANGE_TYPE_COMPANY]
    role_changes = [c for c in changes if c.change_type == CHANGE_TYPE_ROLE]

    company_rows = "".join(_email_company_row(c) for c in company_changes)
    role_rows = "".join(_email_role_row(c) for c in role_changes)

    sections = ""
    if company_changes:
        sections += f"""
          <div style="font-size:13px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:#b3261e;margin:0 0 10px 0;">
            Employer changes ({len(company_changes)})
          </div>
          {company_rows}"""
    if role_changes:
        top_margin = "20px" if company_changes else "0"
        sections += f"""
          <div style="font-size:13px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:#0b57d0;margin:{top_margin} 0 10px 0;">
            Internal mobility ({len(role_changes)})
          </div>
          {role_rows}"""
    if not sections:
        sections = _empty_row_html()

    total = len(changes)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>FactSet Client Watch - Weekly alerts</title></head>
<body style="margin:0;padding:0;background:#f4f5f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;color:#1a1f36;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="640" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
        <tr><td style="background:#0f2645;padding:24px 28px;color:#ffffff;">
          <div style="font-size:12px;letter-spacing:1.5px;text-transform:uppercase;opacity:0.7;">FactSet Client Watch</div>
          <div style="font-size:22px;font-weight:600;margin-top:6px;">Weekly alerts - user movements</div>
          <div style="font-size:14px;opacity:0.8;margin-top:4px;">{total} movement(s) detected on your FactSet users this week</div>
        </td></tr>
        <tr><td style="padding:24px 28px;">
          <p style="margin:0 0 20px 0;font-size:14px;line-height:1.55;color:#3c4257;">
            Hi,<br><br>
            Here are the movements detected this week on the LinkedIn profiles of your FactSet users.
            Two categories: employer changes (retention risk) and internal mobility (relationship opportunity).
          </p>
          {sections}
          <p style="margin:24px 0 0 0;font-size:12px;color:#697386;line-height:1.5;">
            Next run: next Monday.<br>
            Generated by FactSet Client Watch (demo mode).
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _email_company_row(c: Change) -> str:
    name = html.escape(c.full_name)
    prev = html.escape(c.previous_company or "-")
    new = html.escape(c.new_company or "-")
    title = html.escape(c.new_title or "-")
    url = html.escape(c.linkedin_url or "#")
    return f"""
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #f3c3bf;background:#fff8f7;border-radius:8px;margin-bottom:14px;">
          <tr><td style="padding:16px 18px;">
            <div style="font-size:15px;font-weight:600;color:#0f2645;">{name}</div>
            <div style="margin-top:10px;font-size:13px;color:#3c4257;">
              <span style="display:inline-block;background:#fdecea;color:#b3261e;padding:3px 8px;border-radius:4px;font-size:12px;">Previous</span>&nbsp;{prev}
              &nbsp;&rarr;&nbsp;
              <span style="display:inline-block;background:#e6f4ea;color:#137333;padding:3px 8px;border-radius:4px;font-size:12px;">New</span>&nbsp;<strong>{new}</strong>
            </div>
            <div style="margin-top:8px;font-size:13px;color:#697386;">New title: {title}</div>
            <div style="margin-top:12px;">
              <a href="{url}" style="font-size:12px;color:#0a5cff;text-decoration:none;">Open LinkedIn profile &rarr;</a>
            </div>
          </td></tr>
        </table>"""


def _email_role_row(c: Change) -> str:
    name = html.escape(c.full_name)
    company = html.escape(c.new_company or "-")
    prev_title = html.escape(c.previous_title or "-")
    new_title = html.escape(c.new_title or "-")
    url = html.escape(c.linkedin_url or "#")
    return f"""
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #c9d8f5;background:#f4f8ff;border-radius:8px;margin-bottom:14px;">
          <tr><td style="padding:16px 18px;">
            <div style="font-size:15px;font-weight:600;color:#0f2645;">{name}</div>
            <div style="margin-top:10px;font-size:13px;color:#3c4257;">
              <span style="display:inline-block;background:#e6e9ef;color:#3c4257;padding:3px 8px;border-radius:4px;font-size:12px;">Previous title</span>&nbsp;{prev_title}
              &nbsp;&rarr;&nbsp;
              <span style="display:inline-block;background:#e8f0fe;color:#0b57d0;padding:3px 8px;border-radius:4px;font-size:12px;">New title</span>&nbsp;<strong>{new_title}</strong>
            </div>
            <div style="margin-top:8px;font-size:13px;color:#697386;">Still at: {company}</div>
            <div style="margin-top:12px;">
              <a href="{url}" style="font-size:12px;color:#0a5cff;text-decoration:none;">Open LinkedIn profile &rarr;</a>
            </div>
          </td></tr>
        </table>"""


def _empty_row_html() -> str:
    return """<div style="padding:24px;background:#f6f8fa;border-radius:8px;color:#697386;font-size:14px;text-align:center;">
        No movement detected this week.
      </div>"""


def _render_teams_card(changes: list[Change]) -> dict:
    """Build a MessageCard-compatible payload for a Teams incoming webhook."""
    sections = []
    for c in changes:
        if c.change_type == CHANGE_TYPE_ROLE:
            subtitle = f"Internal mobility @ {c.new_company or '?'}"
            facts = [
                {"name": "Previous title", "value": c.previous_title or "-"},
                {"name": "New title", "value": c.new_title or "-"},
                {"name": "Detected on", "value": c.detected_at},
            ]
        else:
            subtitle = f"{c.previous_company or '?'} -> {c.new_company or '?'}"
            facts = [
                {"name": "New title", "value": c.new_title or "-"},
                {"name": "Detected on", "value": c.detected_at},
            ]
        sections.append({
            "activityTitle": c.full_name,
            "activitySubtitle": subtitle,
            "facts": facts,
            "potentialAction": [{
                "@type": "OpenUri",
                "name": "Open LinkedIn profile",
                "targets": [{"os": "default", "uri": c.linkedin_url or "#"}],
            }] if c.linkedin_url else [],
        })

    company_n = sum(1 for c in changes if c.change_type == CHANGE_TYPE_COMPANY)
    role_n = sum(1 for c in changes if c.change_type == CHANGE_TYPE_ROLE)
    return {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": "0F2645",
        "summary": f"FactSet Client Watch - {len(changes)} movement(s)",
        "title": "FactSet Client Watch - weekly alerts",
        "text": (f"{company_n} employer change(s) and {role_n} internal move(s) "
                 "detected on your FactSet users this week."),
        "sections": sections,
    }


def _render_teams_preview_html(changes: list[Change]) -> str:
    """Static HTML that mimics the look of a Teams Adaptive Card render."""
    cards = "".join(_teams_section_html(c) for c in changes) or """
      <div style="padding:20px;color:#616770;">No movement this week.</div>"""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Teams preview - FactSet alerts</title></head>
<body style="margin:0;padding:32px;background:#e6e9ef;font-family:'Segoe UI',-apple-system,BlinkMacSystemFont,Roboto,Arial,sans-serif;color:#252424;">
  <div style="max-width:520px;margin:0 auto;">
    <div style="font-size:13px;color:#616770;margin-bottom:8px;">Microsoft Teams &middot; channel <strong>#account-management</strong></div>
    <div style="background:#ffffff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.12);overflow:hidden;">
      <div style="background:#0f2645;color:#ffffff;padding:14px 18px;">
        <div style="font-size:11px;letter-spacing:1.2px;text-transform:uppercase;opacity:0.75;">Connector &middot; FactSet Client Watch</div>
        <div style="font-size:16px;font-weight:600;margin-top:4px;">Weekly alerts - user movements</div>
      </div>
      <div style="padding:8px 18px 18px 18px;">
        {cards}
      </div>
    </div>
    <div style="font-size:11px;color:#616770;margin-top:10px;">Static preview of the Teams message. In production, this content is sent via an incoming webhook.</div>
  </div>
</body></html>"""


def _teams_section_html(c: Change) -> str:
    name = html.escape(c.full_name)
    url = html.escape(c.linkedin_url or "#")
    if c.change_type == CHANGE_TYPE_ROLE:
        tag = ('<span style="background:#e8f0fe;color:#0b57d0;padding:2px 7px;border-radius:999px;'
               'font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;'
               'margin-right:6px;">Internal mobility</span>')
        line = (f'{html.escape(c.previous_title or "-")} &rarr; '
                f'<strong style="color:#252424;">{html.escape(c.new_title or "-")}</strong>')
        detail = f'Still at: {html.escape(c.new_company or "-")}'
    else:
        tag = ('<span style="background:#fdecea;color:#b3261e;padding:2px 7px;border-radius:999px;'
               'font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;'
               'margin-right:6px;">Employer change</span>')
        line = (f'{html.escape(c.previous_company or "-")} &rarr; '
                f'<strong style="color:#252424;">{html.escape(c.new_company or "-")}</strong>')
        detail = f'New title: {html.escape(c.new_title or "-")}'
    return f"""
        <div style="border-top:1px solid #edebe9;padding:14px 0;">
          <div style="display:flex;align-items:center;gap:10px;">
            <div style="width:32px;height:32px;border-radius:50%;background:#0f2645;color:#ffffff;display:flex;align-items:center;justify-content:center;font-weight:600;font-size:13px;">
              {html.escape(_initials(c.full_name))}
            </div>
            <div>
              <div style="font-size:14px;font-weight:600;">{tag}{name}</div>
              <div style="font-size:12px;color:#616770;margin-top:2px;">{line}</div>
            </div>
          </div>
          <div style="font-size:12px;color:#616770;margin:8px 0 0 42px;">{detail}</div>
          <div style="margin:10px 0 0 42px;">
            <a href="{url}" style="display:inline-block;font-size:12px;color:#ffffff;background:#0a5cff;padding:6px 12px;border-radius:4px;text-decoration:none;">Open LinkedIn profile</a>
          </div>
        </div>"""


def _initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()
