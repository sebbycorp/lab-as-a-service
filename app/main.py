"""Lab-as-a-service portal MVP — student request + admin-only destroy."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import db
from .provision import allocate_tenant, mint_homepage_token, mint_tailscale_for_lab
from . import proxmox_provision

APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")
SESSION_SECRET = os.environ.get("SESSION_SECRET") or secrets.token_hex(32)
PORTAL_PUBLIC_URL = os.environ.get("PORTAL_PUBLIC_URL", "http://127.0.0.1:8080").rstrip("/")

# Hard rule: never expose home LAN in student UI
HOME_LAN = "172.16.10.0/24"
TAILNET_DNS = os.environ.get("LAS_TAILNET_DNS", "tail4736a7.ts.net").lstrip(".")

app = FastAPI(title="Lab as a Service", docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax", https_only=False)
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


def require_admin(request: Request) -> None:
    if not request.session.get("admin"):
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/admin/login"})


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request,
        "home.html",
        {"request": request, "portal_url": PORTAL_PUBLIC_URL},
    )


@app.post("/request")
def request_lab(
    request: Request,
    student_name: str = Form(...),
    student_email: str = Form(...),
):
    name = student_name.strip()
    email = student_email.strip().lower()
    if not name or "@" not in email:
        raise HTTPException(400, "Name and valid email required")
    now = db.utcnow()
    with db.connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO labs (student_name, student_email, status, homepage_token, created_at, updated_at)
            VALUES (?, ?, 'requested', ?, ?, ?)
            """,
            (name, email, mint_homepage_token(), now, now),
        )
        lab_id = cur.lastrowid
    return RedirectResponse(f"/lab/{lab_id}?email={email}", status_code=303)


@app.get("/lab/{lab_id}", response_class=HTMLResponse)
def lab_status(request: Request, lab_id: int, email: str = ""):
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM labs WHERE id = ?", (lab_id,)).fetchone()
    lab = db.row_to_dict(row)
    if not lab or lab["status"] == "destroyed":
        raise HTTPException(404, "Lab not found")
    # Light gate: email query must match (MVP; SSO later)
    if email and email.strip().lower() != lab["student_email"]:
        raise HTTPException(403, "Email does not match this lab")
    return templates.TemplateResponse(
        request,
        "lab_status.html",
        {
            "request": request,
            "lab": lab,
            "portal_url": PORTAL_PUBLIC_URL,
            "home_lan_blocked": HOME_LAN,
        },
    )


@app.get("/h/{token}", response_class=HTMLResponse)
def student_homepage(request: Request, token: str):
    """Per-student links page (Homepage-style cards). No destroy."""
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM labs WHERE homepage_token = ? AND status != 'destroyed'",
            (token,),
        ).fetchone()
    lab = db.row_to_dict(row)
    if not lab:
        raise HTTPException(404, "Unknown or destroyed lab")
    slug = (lab.get("tenant_slug") or "").strip()
    access_short = f"{slug}-access" if slug else ""
    access_host = f"{access_short}.{TAILNET_DNS}" if access_short else ""
    pa_ip = lab.get("pa_ip") or "192.168.1.254"
    client_ip = lab.get("client_ip") or "192.168.1.20"
    novnc_url = (
        f"http://{access_short}:6080/vnc.html?autoconnect=1&resize=remote"
        if access_short
        else ""
    )
    firewall_url = f"https://{access_short}:8443" if access_short else ""
    return templates.TemplateResponse(
        request,
        "student_home.html",
        {
            "request": request,
            "lab": lab,
            "portal_url": PORTAL_PUBLIC_URL,
            "access_short": access_short,
            "access_host": access_host,
            "pa_ip": pa_ip,
            "client_ip": client_ip,
            "novnc_url": novnc_url,
            "firewall_url": firewall_url,
        },
    )


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_form(request: Request):
    return templates.TemplateResponse(
        request,
        "admin_login.html",
        {"request": request, "error": None},
    )


@app.post("/admin/login")
def admin_login(request: Request, password: str = Form(...)):
    if password != ADMIN_PASSWORD:
        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {"request": request, "error": "Wrong password"},
            status_code=401,
        )
    request.session["admin"] = True
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/logout")
def admin_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse("/admin/login", status_code=303)
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM labs WHERE status != 'destroyed' ORDER BY id DESC"
        ).fetchall()
        destroyed = conn.execute(
            "SELECT COUNT(*) AS c FROM labs WHERE status = 'destroyed'"
        ).fetchone()["c"]
    labs = [dict(r) for r in rows]
    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "request": request,
            "labs": labs,
            "destroyed_count": destroyed,
            "portal_url": PORTAL_PUBLIC_URL,
        },
    )




@app.get("/admin/tailscale-acl", response_class=HTMLResponse)
def admin_tailscale_acl(request: Request):
    if not request.session.get("admin"):
        return RedirectResponse("/admin/login", status_code=303)
    from . import tailscale
    status = "API ready (tskey-api-)" if tailscale.configured() else (
        "Have tskey-auth- only — need API token" if tailscale.auth_key_only() else "No Tailscale key configured"
    )
    return templates.TemplateResponse(
        request,
        "admin_tailscale.html",
        {
            "request": request,
            "status": status,
            "fragment": tailscale.acl_policy_fragment(),
            "portal_url": PORTAL_PUBLIC_URL,
        },
    )

@app.post("/admin/labs/{lab_id}/approve")
def admin_approve(request: Request, lab_id: int):
    if not request.session.get("admin"):
        return RedirectResponse("/admin/login", status_code=303)
    alloc = allocate_tenant(lab_id)
    ts = mint_tailscale_for_lab(alloc["tenant_slug"], alloc["trust_cidr"])
    prov_notes = ""
    try:
        prov = proxmox_provision.provision_tenant(lab_id, alloc["tenant_slug"])
        if not prov.get("skipped"):
            # Prefer real academy IPs when provisioned
            if prov.get("pa_ip"):
                alloc["pa_ip"] = prov["pa_ip"]
            if prov.get("client_ip"):
                alloc["client_ip"] = prov["client_ip"]
            if prov.get("trust_lab"):
                alloc["trust_cidr"] = prov["trust_lab"]
            prov_notes = " Provisioned: " + ", ".join(f"{k}={prov[k]}" for k in ("vmid_pa","vmid_client","ctid_access","bridge_trust") if k in prov)
        else:
            prov_notes = " Provision skipped (LAS_PROVISION off)."
    except Exception as e:
        prov_notes = f" Provision error: {e}"
    now = db.utcnow()
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM labs WHERE id = ?", (lab_id,)).fetchone()
        if not row or row["status"] == "destroyed":
            raise HTTPException(404)
        conn.execute(
            """
            UPDATE labs SET
              status = 'ready',
              tenant_slug = ?,
              vmid_base = ?,
              trust_cidr = ?,
              client_ip = ?,
              pa_ip = ?,
              tailscale_auth_key = ?,
              tailscale_notes = ?,
              admin_notes = ?,
              updated_at = ?
            WHERE id = ?
            """,
            (
                alloc["tenant_slug"],
                alloc["vmid_base"],
                alloc["trust_cidr"],
                alloc["client_ip"],
                alloc["pa_ip"],
                ts["tailscale_auth_key"],
                ts["tailscale_notes"],
                alloc["notes"] + " Bridges: " + ", ".join(alloc["bridges"]) + prov_notes,
                now,
                lab_id,
            ),
        )
    return RedirectResponse("/admin", status_code=303)



@app.post("/admin/labs/{lab_id}/remint-ts")
def admin_remint_ts(request: Request, lab_id: int):
    if not request.session.get("admin"):
        return RedirectResponse("/admin/login", status_code=303)
    now = db.utcnow()
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM labs WHERE id = ?", (lab_id,)).fetchone()
        if not row or row["status"] == "destroyed":
            raise HTTPException(404)
        slug = row["tenant_slug"] or f"lab{lab_id}"
        cidr = row["trust_cidr"] or "192.168.1.0/24"
        ts = mint_tailscale_for_lab(slug, cidr)
        conn.execute(
            """
            UPDATE labs SET
              tailscale_auth_key = ?,
              tailscale_notes = ?,
              updated_at = ?
            WHERE id = ?
            """,
            (ts["tailscale_auth_key"], ts["tailscale_notes"], now, lab_id),
        )
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/labs/{lab_id}/stop")
def admin_stop(request: Request, lab_id: int):
    if not request.session.get("admin"):
        return RedirectResponse("/admin/login", status_code=303)
    now = db.utcnow()
    with db.connect() as conn:
        conn.execute(
            "UPDATE labs SET status = 'stopped', updated_at = ? WHERE id = ? AND status != 'destroyed'",
            (now, lab_id),
        )
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/labs/{lab_id}/start")
def admin_start(request: Request, lab_id: int):
    if not request.session.get("admin"):
        return RedirectResponse("/admin/login", status_code=303)
    now = db.utcnow()
    with db.connect() as conn:
        conn.execute(
            "UPDATE labs SET status = 'ready', updated_at = ? WHERE id = ? AND status = 'stopped'",
            (now, lab_id),
        )
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/labs/{lab_id}/destroy")
def admin_destroy(request: Request, lab_id: int):
    """Admin-only destroy. Students have no route to this."""
    if not request.session.get("admin"):
        return RedirectResponse("/admin/login", status_code=303)
    now = db.utcnow()
    with db.connect() as conn:
        conn.execute(
            """
            UPDATE labs SET
              status = 'destroyed',
              destroyed_at = ?,
              updated_at = ?,
              tailscale_auth_key = '',
              admin_notes = COALESCE(admin_notes,'') || ' [destroyed by admin]'
            WHERE id = ? AND status != 'destroyed'
            """,
            (now, now, lab_id),
        )
    try:
        proxmox_provision.destroy_tenant(lab_id)
    except Exception:
        pass
    return RedirectResponse("/admin", status_code=303)
