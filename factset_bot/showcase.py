"""Single-page tabbed HTML that bundles the dashboard + email + Teams previews.

This is the file a sales manager loads to experience the demo without any
Python setup. Each preview is embedded in its own <iframe srcdoc="…"> so
their local styles never collide with the shell.
"""
from __future__ import annotations

import html
from pathlib import Path


def _shell_body(dashboard_html: str, email_html: str, teams_html: str,
                generated_at: str) -> str:
    """Return everything that goes inside <body>. No <!doctype>/<html>/<body>."""
    esc_dashboard = html.escape(dashboard_html, quote=True)
    esc_email = html.escape(email_html, quote=True)
    esc_teams = html.escape(teams_html, quote=True)
    return f"""<style>
:root {{
  --bg:#f5f6f8; --ink:#0f172a; --muted:#64748b;
  --brand:#0f2645; --card:#ffffff; --border:#e5e7eb;
  --accent:#0a5cff;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:0; background:var(--bg); color:var(--ink);
        font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif; }}
.shell {{ min-height:100vh; display:flex; flex-direction:column; }}
.top {{ background:var(--brand); color:#ffffff; padding:20px 28px; }}
.top-row {{ display:flex; align-items:center; justify-content:space-between; gap:20px; flex-wrap:wrap; }}
.brand {{ font-size:11px; letter-spacing:2px; text-transform:uppercase; opacity:.75; }}
.title {{ font-size:22px; font-weight:600; margin-top:2px; }}
.subtitle {{ font-size:12.5px; opacity:.72; margin-top:2px; }}
.demo-pill {{ display:inline-block; background:#fff4d6; color:#8a5a00;
               padding:3px 10px; border-radius:999px; font-size:11px;
               font-weight:600; margin-left:8px; vertical-align:middle; }}
nav.tabs {{ display:inline-flex; background:rgba(255,255,255,.08); padding:4px;
            border-radius:10px; gap:2px; }}
nav.tabs button {{ background:transparent; color:#ffffff; border:0;
                    padding:8px 16px; border-radius:8px; font-size:13px;
                    font-weight:500; cursor:pointer;
                    font-family:inherit; letter-spacing:.2px; }}
nav.tabs button.active {{ background:#ffffff; color:var(--brand); font-weight:600; }}
nav.tabs button:not(.active):hover {{ background:rgba(255,255,255,.12); }}
nav.tabs button:focus-visible {{ outline:2px solid #93c5fd; outline-offset:1px; }}
.panels {{ flex:1; padding:16px 28px 28px 28px; }}
.panel {{ display:none; background:var(--card); border:1px solid var(--border);
          border-radius:12px; overflow:hidden; box-shadow:0 1px 3px rgba(15,23,42,.05); }}
.panel.active {{ display:block; }}
.panel iframe {{ border:0; width:100%; display:block; background:#ffffff; }}
.panel-note {{ padding:14px 20px; border-top:1px solid var(--border);
               background:#f8fafc; color:var(--muted); font-size:12.5px;
               display:flex; align-items:center; gap:8px; flex-wrap:wrap; }}
.panel-note strong {{ color:var(--ink); font-weight:600; }}
.foot {{ text-align:center; color:var(--muted); font-size:11.5px; padding:12px 28px 24px 28px; }}
@media (max-width:640px) {{
  .top-row {{ flex-direction:column; align-items:flex-start; }}
  .panels {{ padding:12px 14px 20px 14px; }}
}}
</style>

<div class="shell">
  <header class="top">
    <div class="top-row">
      <div>
        <div class="brand">FactSet Client Watch</div>
        <div class="title">Weekly alerts <span class="demo-pill">Demo</span></div>
        <div class="subtitle">Simulated run &middot; {html.escape(generated_at)}</div>
      </div>
      <nav class="tabs" role="tablist" aria-label="Preview">
        <button type="button" role="tab" data-tab="dashboard" class="active" aria-selected="true">Dashboard</button>
        <button type="button" role="tab" data-tab="email" aria-selected="false">Email digest</button>
        <button type="button" role="tab" data-tab="teams" aria-selected="false">Microsoft Teams</button>
      </nav>
    </div>
  </header>

  <main class="panels">
    <div class="panel active" data-panel="dashboard" role="tabpanel">
      <iframe title="Dashboard preview" srcdoc="{esc_dashboard}" style="height:1400px;"></iframe>
      <div class="panel-note"><strong>Manager view.</strong>
        20 FactSet users monitored. Alerts weighted equally, ordered by detection time.
        Each employer change is enriched with a Salesforce lookup on the destination company.</div>
    </div>
    <div class="panel" data-panel="email" role="tabpanel">
      <iframe title="Email digest preview" srcdoc="{esc_email}" style="height:1400px;"></iframe>
      <div class="panel-note"><strong>Weekly digest email.</strong>
        Sent every Monday to the account-management team via SMTP.</div>
    </div>
    <div class="panel" data-panel="teams" role="tabpanel">
      <iframe title="Microsoft Teams preview" srcdoc="{esc_teams}" style="height:900px;"></iframe>
      <div class="panel-note"><strong>Microsoft Teams card.</strong>
        Posted to the account-management channel via an incoming webhook.</div>
    </div>
  </main>

  <footer class="foot">
    All data on this page is fictional, generated for demonstration purposes.
    In production, users come from Salesforce, LinkedIn signal comes from a compliant enrichment
    provider (Coresignal, People Data Labs, or LinkedIn's SNAP API), and the destination-employer
    status is verified against the Salesforce Account object.
  </footer>
</div>

<script>
(function () {{
  var buttons = document.querySelectorAll('nav.tabs button');
  var panels = document.querySelectorAll('.panel');
  buttons.forEach(function (btn) {{
    btn.addEventListener('click', function () {{
      var target = btn.getAttribute('data-tab');
      buttons.forEach(function (b) {{
        var active = b === btn;
        b.classList.toggle('active', active);
        b.setAttribute('aria-selected', active ? 'true' : 'false');
      }});
      panels.forEach(function (p) {{
        p.classList.toggle('active', p.getAttribute('data-panel') === target);
      }});
    }});
  }});
  // Fit each iframe to its content once it loads (each panel has one).
  document.querySelectorAll('iframe').forEach(function (frame) {{
    frame.addEventListener('load', function () {{
      try {{
        var doc = frame.contentDocument;
        if (doc && doc.documentElement) {{
          var h = Math.max(doc.documentElement.scrollHeight, doc.body.scrollHeight);
          frame.style.height = (h + 8) + 'px';
        }}
      }} catch (e) {{ /* srcdoc same-origin, but guard anyway */ }}
    }});
  }});
}})();
</script>"""


def render_showcase(dashboard_html_path: Path, email_html_path: Path,
                    teams_html_path: Path, out_path: Path,
                    generated_at: str) -> Path:
    """Combine the three previews into a single-page tabbed HTML file."""
    dashboard = dashboard_html_path.read_text(encoding="utf-8")
    email = email_html_path.read_text(encoding="utf-8")
    teams = teams_html_path.read_text(encoding="utf-8")
    body = _shell_body(dashboard, email, teams, generated_at)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    full_page = (
        "<!doctype html>\n"
        '<html lang="en"><head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        "<title>FactSet Client Watch - Demo showcase</title>\n"
        "</head><body>\n"
        f"{body}\n"
        "</body></html>\n"
    )
    out_path.write_text(full_page, encoding="utf-8")

    artifact_path = out_path.with_name("showcase_artifact_body.html")
    artifact_path.write_text(body, encoding="utf-8")
    return out_path
