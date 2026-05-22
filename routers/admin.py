"""
Admin dashboard — /admin
Password-protected. Set ADMIN_PASSWORD env var (default: nova2024).
"""
import os
import re
import secrets
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

import db
from services.vapi_provisioner import provision

router = APIRouter(prefix="/admin")
_security = HTTPBasic()
_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "nova2024")
SERVER_BASE_URL = os.environ.get("SERVER_BASE_URL", "https://web-production-0209e.up.railway.app")


def _auth(creds: HTTPBasicCredentials = Depends(_security)):
    ok = (
        secrets.compare_digest(creds.username, "admin") and
        secrets.compare_digest(creds.password, _ADMIN_PASSWORD)
    )
    if not ok:
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Basic"})


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


VAPI_PUBLIC_KEY = os.environ.get("VAPI_PUBLIC_KEY", "")

_CSS = """
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f5f7fa; color: #333; }
  header { background: #1a56db; color: #fff; padding: 16px 24px;
           display: flex; justify-content: space-between; align-items: center; }
  header h1 { font-size: 1.2rem; font-weight: 600; }
  .container { max-width: 1100px; margin: 24px auto; padding: 0 16px; }
  .card { background: #fff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,.1);
          padding: 20px; margin-bottom: 20px; }
  .card-header { display: flex; justify-content: space-between; align-items: center;
                 margin-bottom: 16px; }
  .card-header h2 { font-size: 1rem; font-weight: 600; }
  table { width: 100%; border-collapse: collapse; font-size: .9rem; }
  th { background: #f1f5f9; padding: 10px 12px; text-align: left;
       font-weight: 600; border-bottom: 2px solid #e2e8f0; }
  td { padding: 10px 12px; border-bottom: 1px solid #e2e8f0; vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 99px;
           font-size: .75rem; font-weight: 600; }
  .badge-green  { background: #d1fae5; color: #065f46; }
  .badge-yellow { background: #fef3c7; color: #92400e; }
  .badge-gray   { background: #e2e8f0; color: #475569; }
  .btn { display: inline-block; padding: 6px 14px; border-radius: 6px; font-size: .85rem;
         font-weight: 500; cursor: pointer; border: none; text-decoration: none; }
  .btn-primary  { background: #1a56db; color: #fff; }
  .btn-success  { background: #059669; color: #fff; }
  .btn-warning  { background: #d97706; color: #fff; }
  .btn-danger   { background: #dc2626; color: #fff; }
  .btn + .btn   { margin-left: 6px; }
  .btn:hover    { opacity: .85; }
  .modal-bg { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.4);
              z-index: 100; align-items: center; justify-content: center; }
  .modal-bg.open { display: flex; }
  .modal { background: #fff; border-radius: 10px; padding: 24px; width: 600px;
           max-width: 95vw; max-height: 90vh; overflow-y: auto; }
  .modal h3 { font-size: 1.1rem; margin-bottom: 16px; }
  .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .form-full { grid-column: 1 / -1; }
  label { display: block; font-size: .82rem; font-weight: 600; margin-bottom: 4px; color: #555; }
  input, textarea { width: 100%; padding: 8px 10px; border: 1px solid #d1d5db;
                    border-radius: 6px; font-size: .9rem; }
  textarea { height: 60px; resize: vertical; }
  .form-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
  .url-box { background: #f1f5f9; border-radius: 6px; padding: 8px 12px;
             font-size: .78rem; font-family: monospace; word-break: break-all; }
  .widget-modal { background: #fff; border-radius: 10px; padding: 24px;
                  width: 700px; max-width: 95vw; max-height: 90vh; overflow-y: auto; }
  .code-block { background: #1e1e2e; color: #cdd6f4; border-radius: 8px; padding: 16px;
                font-family: monospace; font-size: .8rem; white-space: pre; overflow-x: auto;
                line-height: 1.5; }
  .copy-btn { background: #1a56db; color: #fff; border: none; padding: 6px 14px;
              border-radius: 6px; cursor: pointer; font-size: .82rem; margin-top: 8px; }
</style>
"""

_MODAL = """
<div class="modal-bg" id="modal">
  <div class="modal">
    <h3 id="modal-title">Add Business</h3>
    <form method="post" action="/admin/save">
      <input type="hidden" name="original_id" id="original_id">
      <div class="form-grid">
        <div>
          <label>Business ID (slug)</label>
          <input name="id" id="f-id" placeholder="bright-smiles" required>
        </div>
        <div>
          <label>Business Name</label>
          <input name="name" id="f-name" placeholder="Bright Smiles Dental" required>
        </div>
        <div>
          <label>Phone</label>
          <input name="phone" id="f-phone" placeholder="+17035551234">
        </div>
        <div>
          <label>Owner Email (notifications sent here)</label>
          <input name="owner_email" id="f-email" placeholder="owner@clinic.com" required>
        </div>
        <div class="form-full">
          <label>Address</label>
          <input name="address" id="f-address" placeholder="1234 Main St, McLean, VA 22101">
        </div>
        <div>
          <label>Hours Mon–Fri</label>
          <input name="hours_mon_fri" id="f-hmf" placeholder="8:00 AM - 6:00 PM">
        </div>
        <div>
          <label>Hours Saturday</label>
          <input name="hours_sat" id="f-hsat" placeholder="9:00 AM - 2:00 PM">
        </div>
        <div>
          <label>Hours Sunday</label>
          <input name="hours_sun" id="f-hsun" placeholder="Closed">
        </div>
        <div class="form-full">
          <label>Services (comma-separated)</label>
          <textarea name="services" id="f-services" placeholder="General dentistry, cleanings, fillings..."></textarea>
        </div>
        <div class="form-full">
          <label>Insurance Accepted (comma-separated)</label>
          <textarea name="insurance" id="f-insurance" placeholder="Delta Dental, MetLife, Cigna..."></textarea>
        </div>
        <div>
          <label>Agent Name (receptionist name callers hear)</label>
          <input name="agent_name" id="f-agent" placeholder="Aria">
        </div>
        <div>
          <label>Assistant Name (label in VAPI dashboard)</label>
          <input name="assistant_name" id="f-asst" placeholder="Aria — Bright Smiles Dental">
        </div>
        <div class="form-full">
          <label>First Message (optional)</label>
          <input name="first_message" id="f-first" placeholder="Thank you for calling...">
        </div>
      </div>
      <div class="form-actions">
        <button type="button" class="btn btn-danger" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary">Save</button>
      </div>
    </form>
  </div>
</div>
<script>
function openAdd() {
  document.getElementById('modal-title').textContent = 'Add Business';
  ['id','name','phone','email','address','hmf','hsat','hsun','services','insurance','asst','first']
    .forEach(k => { const el = document.getElementById('f-'+k); if(el) el.value=''; });
  document.getElementById('f-hmf').value = '8:00 AM - 6:00 PM';
  document.getElementById('f-hsat').value = '9:00 AM - 2:00 PM';
  document.getElementById('f-hsun').value = 'Closed';
  document.getElementById('original_id').value = '';
  document.getElementById('modal').classList.add('open');
}
function openEdit(d) {
  document.getElementById('modal-title').textContent = 'Edit Business';
  document.getElementById('original_id').value = d.id;
  document.getElementById('f-id').value = d.id;
  document.getElementById('f-name').value = d.name;
  document.getElementById('f-phone').value = d.phone;
  document.getElementById('f-email').value = d.owner_email;
  document.getElementById('f-address').value = d.address;
  document.getElementById('f-hmf').value = d.hours_mon_fri;
  document.getElementById('f-hsat').value = d.hours_sat;
  document.getElementById('f-hsun').value = d.hours_sun;
  document.getElementById('f-services').value = d.services;
  document.getElementById('f-insurance').value = d.insurance;
  document.getElementById('f-agent').value = d.agent_name || 'Aria';
  document.getElementById('f-asst').value = d.assistant_name;
  document.getElementById('f-first').value = d.first_message;
  document.getElementById('modal').classList.add('open');
}
function closeModal() {
  document.getElementById('modal').classList.remove('open');
}
document.getElementById('modal').addEventListener('click', function(e){
  if(e.target === this) closeModal();
});
</script>
"""


def _render(businesses: list, flash: str = "") -> str:
    rows = ""
    for b in businesses:
        vapi_id = b.get("vapi_assistant_id", "")
        vapi_badge = (
            f'<span class="badge badge-green">Provisioned</span>' if vapi_id
            else '<span class="badge badge-yellow">Not provisioned</span>'
        )
        status_badge = (
            '<span class="badge badge-green">Active</span>' if b.get("active", 1)
            else '<span class="badge badge-gray">Inactive</span>'
        )
        webhook = f"{SERVER_BASE_URL}/vapi/{b['id']}/webhook"
        llm_url = f"{SERVER_BASE_URL}/llm/{b['id']}/v1/chat/completions"

        import json as _json
        bdata = _json.dumps({k: b.get(k, "") for k in
            ["id","name","phone","owner_email","address","hours_mon_fri","hours_sat",
             "hours_sun","services","insurance","assistant_name","first_message"]
        }, ensure_ascii=False).replace("'", "\\'").replace('"', '&quot;')

        widget_code = f"""<!-- Nova Voice Agent Widget — {b['name']} -->
<script>
  (function (d, t) {{
    var g = d.createElement(t), s = d.getElementsByTagName(t)[0];
    g.src = "https://cdn.jsdelivr.net/gh/VapiAI/html-script-tag@latest/dist/assets/index.js";
    g.defer = true; g.async = true;
    s.parentNode.insertBefore(g, s);
    g.onload = function () {{
      window.vapiSDK.run({{
        apiKey: "{VAPI_PUBLIC_KEY or 'YOUR_VAPI_PUBLIC_KEY'}",
        assistant: "{vapi_id or 'PROVISION_VAPI_FIRST'}",
        config: {{
          position: "bottom-right",
          offset: "40px",
          width: "56px",
          height: "56px",
          idle: {{
            color: "#1a56db",
            type: "pill",
            title: "Call Us",
            subtitle: "Available 24/7",
            icon: "https://unpkg.com/lucide-static@0.321.0/icons/phone.svg"
          }},
          loading: {{ color: "#1a56db", type: "pill", title: "Connecting..." }},
          active: {{
            color: "#dc2626",
            type: "pill",
            title: "Call in progress",
            subtitle: "Tap to end",
            icon: "https://unpkg.com/lucide-static@0.321.0/icons/phone-off.svg"
          }}
        }}
      }});
    }};
  }})(document, "script");
</script>"""

        widget_escaped = widget_code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        rows += f"""
        <tr>
          <td><strong>{b['name']}</strong><br>
              <span style="color:#888;font-size:.8rem">{b['id']}</span></td>
          <td>{b.get('owner_email','')}</td>
          <td>{status_badge}</td>
          <td>{vapi_badge}<br>
              <span style="color:#888;font-size:.75rem">{vapi_id[:20] + '…' if len(vapi_id) > 20 else vapi_id}</span></td>
          <td>
            <button class="btn btn-primary" onclick='openEdit({bdata})'>Edit</button>
            <form method="post" action="/admin/provision/{b['id']}" style="display:inline">
              <button type="submit" class="btn btn-success">Provision VAPI</button>
            </form>
            <button class="btn btn-warning" onclick="openWidget('{b['id']}', `{widget_code.replace('`','\\`')}`)">Get Widget</button>
            <form method="post" action="/admin/delete/{b['id']}" style="display:inline"
                  onsubmit="return confirm('Delete {b['name']}?')">
              <button type="submit" class="btn btn-danger">Delete</button>
            </form>
            <details style="margin-top:6px;font-size:.8rem">
              <summary style="cursor:pointer;color:#1a56db">Show URLs</summary>
              <div style="margin-top:6px">
                <div style="margin-bottom:4px"><b>Webhook:</b></div>
                <div class="url-box">{webhook}</div>
                <div style="margin:6px 0 4px"><b>LLM URL:</b></div>
                <div class="url-box">{llm_url}</div>
              </div>
            </details>
          </td>
        </tr>"""

    flash_html = f'<div style="background:#d1fae5;border:1px solid #6ee7b7;border-radius:6px;padding:10px 14px;margin-bottom:16px;color:#065f46">{flash}</div>' if flash else ""

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Nova Admin Dashboard</title>{_CSS}</head><body>
<header>
  <h1>Nova Voice Agent — Admin Dashboard</h1>
  <span style="font-size:.85rem;opacity:.8">{SERVER_BASE_URL}</span>
</header>
<div class="container">
  {flash_html}
  <div class="card">
    <div class="card-header">
      <h2>Businesses ({len(businesses)})</h2>
      <button class="btn btn-primary" onclick="openAdd()">+ Add Business</button>
    </div>
    <table>
      <thead><tr>
        <th>Business</th><th>Owner Email</th><th>Status</th>
        <th>VAPI Assistant</th><th>Actions</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
  <div class="card" style="font-size:.85rem;color:#666">
    <strong>How it works:</strong> Each business gets its own VAPI assistant with a unique
    webhook and LLM URL. Click <em>Provision VAPI</em> after adding or editing a business
    to create/update the assistant in VAPI. The agent then answers calls for that business
    using their specific info, hours, and notification email.
  </div>
</div>
{_MODAL}

<!-- Widget Code Modal -->
<div class="modal-bg" id="widget-modal">
  <div class="widget-modal">
    <h3 style="margin-bottom:4px">Website Widget Code</h3>
    <p style="color:#6b7280;font-size:.85rem;margin-bottom:14px">
      Paste this snippet just before the <code>&lt;/body&gt;</code> tag on the client's website.
      It adds a floating "Call Us" button that connects directly to Nova.
    </p>
    <div id="widget-name" style="font-weight:600;margin-bottom:8px;color:#1a56db"></div>

    {'<div style="background:#fef3c7;border:1px solid #fbbf24;border-radius:6px;padding:10px 14px;font-size:.82rem;margin-bottom:12px"><strong>⚠ Set your VAPI Public Key:</strong> Add <code>VAPI_PUBLIC_KEY</code> in Railway env vars. Get it from <a href="https://dashboard.vapi.ai" target="_blank">dashboard.vapi.ai</a> → Account → Public Key.</div>' if not VAPI_PUBLIC_KEY else ''}

    <pre class="code-block" id="widget-code-display"></pre>
    <div style="display:flex;gap:8px;margin-top:12px">
      <button class="copy-btn" onclick="copyWidget()">Copy Code</button>
      <button class="btn btn-danger" onclick="closeWidget()" style="margin-left:auto">Close</button>
    </div>

    <div style="margin-top:20px;border-top:1px solid #e5e7eb;padding-top:16px;font-size:.82rem">
      <strong>Phone diversion (no website):</strong> Forward the clinic's phone number to their
      VAPI phone number in your VAPI dashboard. No widget needed — calls route directly to Nova.
    </div>
  </div>
</div>

<script>
var _widgetCode = '';
function openWidget(id, code) {{
  _widgetCode = code;
  document.getElementById('widget-code-display').textContent = code;
  document.getElementById('widget-name').textContent = 'Business: ' + id;
  document.getElementById('widget-modal').classList.add('open');
}}
function closeWidget() {{
  document.getElementById('widget-modal').classList.remove('open');
}}
function copyWidget() {{
  navigator.clipboard.writeText(_widgetCode).then(function() {{
    document.querySelector('.copy-btn').textContent = 'Copied!';
    setTimeout(function() {{ document.querySelector('.copy-btn').textContent = 'Copy Code'; }}, 2000);
  }});
}}
document.getElementById('widget-modal').addEventListener('click', function(e) {{
  if (e.target === this) closeWidget();
}});
</script>

</body></html>"""


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def dashboard(_=Depends(_auth)):
    return _render(db.get_all())


@router.post("/save")
async def save(
    _=Depends(_auth),
    original_id: str = Form(""),
    id: str = Form(...),
    name: str = Form(...),
    phone: str = Form(""),
    owner_email: str = Form(...),
    address: str = Form(""),
    hours_mon_fri: str = Form("8:00 AM - 6:00 PM"),
    hours_sat: str = Form("9:00 AM - 2:00 PM"),
    hours_sun: str = Form("Closed"),
    services: str = Form(""),
    insurance: str = Form(""),
    agent_name: str = Form("Aria"),
    assistant_name: str = Form(""),
    first_message: str = Form(""),
):
    biz_id = id.strip() or _slug(name)
    existing = db.get(original_id) if original_id else None
    vapi_id = existing.get("vapi_assistant_id", "") if existing else ""

    db.upsert({
        "id": biz_id, "name": name, "phone": phone, "owner_email": owner_email,
        "address": address, "hours_mon_fri": hours_mon_fri, "hours_sat": hours_sat,
        "hours_sun": hours_sun, "services": services, "insurance": insurance,
        "agent_name": agent_name or "Aria",
        "assistant_name": assistant_name, "first_message": first_message,
        "vapi_assistant_id": vapi_id, "active": 1,
    })
    if original_id and original_id != biz_id:
        db.delete(original_id)

    return RedirectResponse(f"/admin?saved={biz_id}", status_code=303)


@router.post("/provision/{business_id}", response_class=HTMLResponse)
async def provision_business(business_id: str, _=Depends(_auth)):
    biz = db.get(business_id)
    if not biz:
        return HTMLResponse(f"Business '{business_id}' not found", status_code=404)
    try:
        vapi_id = await provision(biz)
        db.set_vapi_id(business_id, vapi_id)
        flash = f"✓ VAPI assistant provisioned for {biz['name']} (ID: {vapi_id})"
    except Exception as e:
        flash = f"✗ Provisioning failed: {e}"
    return _render(db.get_all(), flash=flash)


@router.post("/delete/{business_id}", response_class=HTMLResponse)
async def delete_business(business_id: str, _=Depends(_auth)):
    biz = db.get(business_id)
    name = biz["name"] if biz else business_id
    db.delete(business_id)
    return _render(db.get_all(), flash=f"Deleted: {name}")
