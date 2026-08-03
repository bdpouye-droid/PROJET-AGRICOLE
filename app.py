# app.py
# PROJET-AGRICOLE - Streamlit app (updated)
# - Téléportation "Y aller"
# - UI modernisée et épurée
# - Montant estimé optionnel
# - Boîte de réception simple (remplacement du rappel)
# - Circuit de validation strict (Achats -> Finance -> DG en suivi)
# - Catégories / tags & ticket #TICK-XXXX
#
# NOTE: Tester localement : `streamlit run app.py`
# Assure-toi d'avoir sqlite3 et Streamlit installés.

import streamlit as st
import sqlite3
from datetime import datetime
import json
import os
import re

# --- Configuration / Utilitaires ---
# Prefer existing canonical DB filename. Use database.db if present, otherwise keep app_data.db for backward compatibility.
base_dir = os.path.dirname(__file__)
if os.path.exists(os.path.join(base_dir, 'database.db')):
    DB_PATH = os.path.join(base_dir, 'database.db')
else:
    DB_PATH = os.path.join(base_dir, 'app_data.db')

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    # demandes table: one row per ticket
    cur.execute("""
    CREATE TABLE IF NOT EXISTS demandes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id TEXT UNIQUE,
        emitter TEXT,
        department TEXT,
        title TEXT,
        description TEXT,
        tags TEXT,
        estimated_amount REAL,
        fournisseur_pressenti TEXT,
        fournisseur_retenu TEXT,
        status TEXT,
        motif_refus TEXT,
        created_at TEXT,
        updated_at TEXT
    )""")
    # inbox entries: simple actionable items (legacy inbox)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inbox_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        ticket_id TEXT,
        message TEXT,
        target_tab TEXT,
        target_sub TEXT,
        created_at TEXT,
        read INTEGER DEFAULT 0
    )""")
    # notifications table (modern inbox) - created to avoid SQL errors when referenced
    cur.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_dept TEXT,
        ticket TEXT,
        message TEXT,
        target_tab TEXT,
        target_disc INTEGER,
        created_at TEXT,
        read INTEGER DEFAULT 0
    )""")
    # logs audit
    cur.execute("""
    CREATE TABLE IF NOT EXISTS logs_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id TEXT,
        user TEXT,
        action TEXT,
        details TEXT,
        created_at TEXT
    )""")
    # metadata for ticket sequence
    cur.execute("""
    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    # connections / pointage (login/logout events)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS connections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        event TEXT,
        created_at TEXT
    )""")
    # init ticket counter if missing
    cur.execute("INSERT OR IGNORE INTO metadata (key, value) VALUES ('ticket_counter', '0')")
    conn.commit()
    conn.close()

def next_ticket_id():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM metadata WHERE key='ticket_counter'")
    row = cur.fetchone()
    counter = int(row['value'])
    counter += 1
    ticket = f"#TICK-{counter:04d}"
    cur.execute("UPDATE metadata SET value = ? WHERE key='ticket_counter'", (str(counter),))
    conn.commit()
    conn.close()
    return ticket

def add_demande(emitter, department, title, description, tags_list, estimated_amount, fournisseur_pressenti):
    ticket = next_ticket_id()
    tags_str = ",".join([t.strip() for t in tags_list if t.strip()])
    now = datetime.utcnow().isoformat()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
      INSERT INTO demandes (ticket_id, emitter, department, title, description, tags, estimated_amount, fournisseur_pressenti, status, created_at, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ticket, emitter, department, title, description, tags_str, estimated_amount, fournisseur_pressenti, "Soumis", now, now))
    conn.commit()
    conn.close()
    # create inbox entries for roles involved: Achats & Finance for workflow
    # Achats should act first for sourcing
    add_inbox_entry("Achats", ticket, f"Nouvelle demande à sourcer: {title}", target_tab="Achats", target_sub="validation_achats")
    add_inbox_entry("Finance", ticket, f"Demande en attente de traitement financier après Achats", target_tab="Finance", target_sub="en_attente")
    # DG gets only a global follow (read-only) when fully validated later
    add_log(ticket, emitter, "Soumission", f"Demande soumise par {emitter}")
    return ticket

def add_inbox_entry(user, ticket_id, message, target_tab=None, target_sub=None):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute("""
      INSERT INTO inbox_entries (user, ticket_id, message, target_tab, target_sub, created_at)
      VALUES (?, ?, ?, ?, ?, ?)
    """, (user, ticket_id, message, target_tab, target_sub, now))
    conn.commit()
    conn.close()

def mark_inbox_read(entry_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE inbox_entries SET read=1 WHERE id=?", (entry_id,))
    conn.commit()
    conn.close()


def ensure_notifications_table():
    """Ensure the legacy/modern notifications table exists. Safe to call repeatedly."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_dept TEXT,
        ticket TEXT,
        message TEXT,
        target_tab TEXT,
        target_disc INTEGER,
        created_at TEXT,
        read INTEGER DEFAULT 0
    )""")
    conn.commit()
    conn.close()


def add_notification(user_dept, ticket, message, target_tab=None, target_disc=None):
    """Insert a notification into the notifications table. If the table is missing or insertion fails,
    fall back to adding an inbox_entries row so callers still get a deliverable notification.
    """
    # Ensure table exists (defensive - handles older DB without notifications table)
    try:
        ensure_notifications_table()
    except Exception:
        # If creation fails, fall back silently to inbox entry
        add_inbox_entry(user_dept, ticket, message, target_tab=target_tab, target_sub=None)
        return

    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute(
            "INSERT INTO notifications (user_dept, ticket, message, target_tab, target_disc, created_at, read) VALUES (?, ?, ?, ?, ?, ?, 0)",
            (user_dept, ticket, message, target_tab, target_disc, now)
        )
        conn.commit()
    except sqlite3.OperationalError:
        # Table might still not exist in some DB copies; gracefully fallback to inbox_entries
        try:
            add_inbox_entry(user_dept, ticket, message, target_tab=target_tab, target_sub=None)
        except Exception:
            pass
    finally:
        if conn:
            conn.close()

def add_log(ticket_id, user, action, details):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute("""
      INSERT INTO logs_audit (ticket_id, user, action, details, created_at)
      VALUES (?, ?, ?, ?, ?)
    """, (ticket_id, user, action, details, now))
    conn.commit()
    conn.close()


def add_connection_event(user, event):
    """Record a connection/login/logout event for basic pointage.
    Call this when a user changes session identity (simple approximation).
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute("INSERT INTO connections (user, event, created_at) VALUES (?, ?, ?)", (user, event, now))
        conn.commit()
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def delete_demande(ticket_id):
    """Delete a demande and related entries (inbox, logs, notifications) — irreversible.
    Use with caution (Admin/emetteur action only).
    """
    conn = get_conn()
    cur = conn.cursor()
    # remove related inbox_entries
    cur.execute("DELETE FROM inbox_entries WHERE ticket_id=?", (ticket_id,))
    # remove notifications if present
    try:
        cur.execute("DELETE FROM notifications WHERE ticket=?", (ticket_id,))
    except Exception:
        # notifications table may not exist
        pass
    # remove logs
    cur.execute("DELETE FROM logs_audit WHERE ticket_id=?", (ticket_id,))
    # remove the demande itself
    cur.execute("DELETE FROM demandes WHERE ticket_id=?", (ticket_id,))
    conn.commit()
    conn.close()


def export_stats_excel(stats_dict):
    """Export given stats (dict of sheets -> list of dict rows) to an Excel file in-memory.
    Falls back to CSV if pandas/openpyxl not available.
    Returns bytes and filename.
    """
    import io
    try:
        import pandas as pd
    except Exception:
        # fallback: serialize first sheet to CSV
        first_sheet = next(iter(stats_dict.keys()))
        rows = stats_dict[first_sheet]
        buf = io.BytesIO()
        if rows:
            # write CSV header
            header = ','.join(rows[0].keys()) + '\n'
            buf.write(header.encode('utf-8'))
            for r in rows:
                line = ','.join([str(r.get(k, '')) for k in r.keys()]) + '\n'
                buf.write(line.encode('utf-8'))
        filename = 'stats_export.csv'
        return buf.getvalue(), filename

    # Use pandas ExcelWriter but guard against missing openpyxl or write errors
    buf = io.BytesIO()
    try:
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            for sheet, rows in stats_dict.items():
                df = pd.DataFrame(rows)
                df.to_excel(writer, sheet_name=sheet[:31], index=False)
        filename = 'stats_export.xlsx'
        return buf.getvalue(), filename
    except Exception:
        # fallback: produce a combined CSV with sheet separators
        buf = io.BytesIO()
        first = True
        for sheet, rows in stats_dict.items():
            if not first:
                buf.write(b"\n\n")
            first = False
            header = sheet + '\n'
            buf.write(header.encode('utf-8'))
            if rows:
                hdr = ','.join(rows[0].keys()) + '\n'
                buf.write(hdr.encode('utf-8'))
                for r in rows:
                    line = ','.join([str(r.get(k, '')) for k in r.keys()]) + '\n'
                    buf.write(line.encode('utf-8'))
        filename = 'stats_export_fallback.csv'
        return buf.getvalue(), filename


def get_inbox_for(user):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM inbox_entries WHERE user=? ORDER BY created_at DESC", (user,))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_demande_by_ticket(ticket_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM demandes WHERE ticket_id=?", (ticket_id,))
    row = cur.fetchone()
    conn.close()
    return row

def update_demande(ticket_id, **kwargs):
    # kwargs: keys matching columns to update
    if not kwargs:
        return
    conn = get_conn()
    cur = conn.cursor()
    set_clause = ", ".join([f"{k}=?" for k in kwargs.keys()])
    params = list(kwargs.values()) + [ticket_id]
    cur.execute(f"UPDATE demandes SET {set_clause}, updated_at=? WHERE ticket_id=?", params[:-1] + [datetime.utcnow().isoformat(), ticket_id])
    conn.commit()
    conn.close()

def list_demandes(filter_by=None):
    conn = get_conn()
    cur = conn.cursor()
    sql = "SELECT * FROM demandes"
    params = ()
    if filter_by:
        clauses = []
        for k, v in filter_by.items():
            clauses.append(f"{k}=?")
            params += (v,)
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC"
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows

def search_by_tag(tag):
    conn = get_conn()
    cur = conn.cursor()
    like = f"%{tag}%"
    cur.execute("SELECT * FROM demandes WHERE tags LIKE ? ORDER BY created_at DESC", (like,))
    rows = cur.fetchall()
    conn.close()
    return rows

# --- UI helpers & navigation ---
def navigate_to(tab_name, sub=None, ticket_id=None):
    """Navigate to a main tab and map tokenized sub-views to user-facing labels so "Y aller" works.
    Accepts either UI labels (e.g. "Demandes à sourcer") or internal tokens (e.g. "validation_achats").
    """
    # mapping of internal sub tokens -> visible radio labels per main tab
    sub_map = {
        'Achats': {
            'validation_achats': 'Demandes à sourcer',
            'validated': 'Demandes validées Achats',
            'historique': 'Historique'
        },
        'Finance': {
            'en_attente': 'Contrôles & Vérifications'
        },
        'Direction': {
            'dg_view': 'Suivi global'
        }
    }
    # normalize main_tab
    st.session_state['main_tab'] = tab_name or st.session_state.get('main_tab')
    # map sub if token provided
    mapped_sub = sub
    try:
        if sub and isinstance(sub, str) and st.session_state['main_tab'] in sub_map and sub in sub_map[st.session_state['main_tab']]:
            mapped_sub = sub_map[st.session_state['main_tab']][sub]
    except Exception:
        mapped_sub = sub
    st.session_state['sub_view'] = mapped_sub
    st.session_state['selected_ticket'] = ticket_id

def ensure_session_state():
    if 'main_tab' not in st.session_state:
        st.session_state['main_tab'] = "Accueil"
    if 'sub_view' not in st.session_state:
        st.session_state['sub_view'] = None
    if 'current_user' not in st.session_state:
        # default demo user; in production replace with auth
        st.session_state['current_user'] = "Utilisateur"
    if 'selected_ticket' not in st.session_state:
        st.session_state['selected_ticket'] = None

# Minimal modern CSS
def inject_css():
    st.markdown("""
    <style>
      :root { --accent:#0d6efd; --muted:#6c757d; --bg:#f8f9fa; --card:#ffffff; --text:#0b1b2b; }
      .stApp { background: var(--bg); font-family: "Inter", "Segoe UI", sans-serif; color:var(--text); }
      .topbar { padding: 10px 0; display:flex; align-items:center; gap:12px; }
      .brand { font-weight:700; color:var(--accent); font-size:20px; }
      .subtitle { color:var(--muted); font-size:12px; }
      .card { background: var(--card); padding:14px; border-radius:8px; box-shadow:0 1px 4px rgba(16,24,40,0.08); color:var(--text); }
      .small { font-size:13px; color:var(--muted); }
      .ticket { font-weight:600; color:#0b5ed7; }
      .pill { padding:4px 8px; border-radius:999px; background:#eef2ff; color:#3730a3; font-size:12px; }
      button.stButton>button { border-radius: 6px; }
      /* Ensure tables and text are readable (fix red/contrast regressions) */
      table, th, td { color:var(--text) !important; }
      .stAlert, .stError { color: #7a1f1f !important; }
    </style>
    """, unsafe_allow_html=True)

# --- Initialize DB ---
init_db()
ensure_session_state()
inject_css()

# --- Header / Top layout ---
st.sidebar.markdown("## Navigation")
# allow selecting current user (simple impersonation for testing)
user_choice = st.sidebar.selectbox("Vous êtes", ["Utilisateur", "Achats", "Finance", "Direction Générale", "Admin"], index=["Utilisateur","Achats","Finance","Direction Générale","Admin"].index(st.session_state.get('current_user','Utilisateur')) if st.session_state.get('current_user') in ["Utilisateur","Achats","Finance","Direction Générale","Admin"] else 0)
# record a simple connection event when the selected user changes (approx. login)
prev_user = st.session_state.get('current_user')
st.session_state['current_user'] = user_choice
if prev_user != user_choice:
    try:
        add_connection_event(user_choice, 'login')
    except Exception:
        pass
    st.session_state['last_user'] = user_choice

# Sidebar inbox (clean, no remind button)
st.sidebar.markdown("### Boîte de réception")
inbox_rows = get_inbox_for(st.session_state['current_user'])
if not inbox_rows:
    st.sidebar.info("Aucun élément en attente.")
else:
    for row in inbox_rows:
        with st.sidebar.container():
            read_mark = " (lu)" if row['read'] else ""
            st.markdown(f"- **{row['ticket_id']}** {read_mark}")
            st.caption(row['message'])
            cols = st.columns([1,1,1])
            if cols[0].button("Y aller", key=f"go_{row['id']}"):
                # Teleport: set main tab/sub and select ticket
                navigate_to(row['target_tab'] or "Accueil", row['target_sub'], row['ticket_id'])
                # mark read
                mark_inbox_read(row['id'])
                st.experimental_rerun()
            if cols[1].button("Marquer lu", key=f"read_{row['id']}"):
                mark_inbox_read(row['id'])
                st.experimental_rerun()
            if cols[2].button("Voir", key=f"view_{row['id']}"):
                navigate_to("Détail", None, row['ticket_id'])
                mark_inbox_read(row['id'])
                st.experimental_rerun()

st.sidebar.markdown("---")
main_nav = st.sidebar.radio("Sections", ["Accueil", "Soumettre", "Achats", "Finance", "Direction", "Études", "Audit", "Détail", "Paramètres"], index=["Accueil","Soumettre","Achats","Finance","Direction","Études","Audit","Détail","Paramètres"].index(st.session_state['main_tab']) if st.session_state['main_tab'] in ["Accueil","Soumettre","Achats","Finance","Direction","Études","Audit","Détail","Paramètres"] else 0)
st.session_state['main_tab'] = main_nav

# --- Main content ---
st.markdown('<div class="topbar"><div class="brand">PROJET-AGRICOLE</div><div class="subtitle">Gestion des demandes & workflow</div></div>', unsafe_allow_html=True)

def page_accueil():
    st.markdown("### Accueil")
    st.markdown("Bienvenue — utilisez la barre latérale pour naviguer. La boîte de réception indique clairement les actions à faire selon votre rôle.")
    # quick stats
    rows = list_demandes()
    total = len(rows)
    st.markdown(f"- Total demandes : **{total}**")
    st.markdown(f"- Utilisateur actif : **{st.session_state['current_user']}**")

def page_soumettre():
    st.markdown("### Émettre une demande")
    st.markdown("Formulaire simple et épuré — le montant estimé est optionnel.")
    with st.form("form_soumettre", clear_on_submit=False):
        emitter = st.session_state['current_user']
        department = st.selectbox("Département émetteur", ["Achats", "Finance", "Direction Générale", "Ingénierie", "Opérations", "Autre"])
        title = st.text_input("Titre de la demande", max_chars=120)
        description = st.text_area("Description / Cahier des charges", height=160)
        tags = st.text_input("Étiquettes (séparées par des virgules)", placeholder="ex: matériel, urgent, 2026")
        fournisseur_pressenti = st.text_input("Fournisseur pressenti (optionnel)")
        # Estimated amount optional
        est_amt = st.number_input("Montant estimé (optionnel)", min_value=0.0, step=1.0, format="%.2f")
        if est_amt == 0.0:
            estimated_amount = None
        else:
            estimated_amount = float(est_amt)
        submitted = st.form_submit_button("Soumettre la demande")
        if submitted:
            if not title or not description:
                st.error("Le titre et la description sont requis.")
            else:
                tags_list = [t.strip() for t in tags.split(",")] if tags else []
                ticket = add_demande(emitter, department, title, description, tags_list, estimated_amount, fournisseur_pressenti)
                st.success(f"Demande envoyée — {ticket}")
                st.balloons()
                # add a confirmation inbox entry for the emitter so the notification is visible in inbox
                try:
                    add_inbox_entry(st.session_state['current_user'], ticket, f"Demande {ticket} soumise avec succès.", target_tab="Détail")
                except Exception:
                    pass
                # clear the form fields by resetting widget states
                st.experimental_rerun()

def render_demande_card(row, show_actions=False):
    ticket = row['ticket_id']
    st.markdown(f"<div class='card'><div style='display:flex;justify-content:space-between;align-items:center;'>"
                f"<div><span class='ticket'>{ticket}</span> — <strong>{row['title']}</strong><div class='small'>{row['description'][:160]}{'...' if len(row['description'])>160 else ''}</div></div>"
                f"<div style='text-align:right'><div class='pill'>{row['status']}</div><div class='small'>Créé: {row['created_at'][:10]}</div></div></div></div>", unsafe_allow_html=True)
    if show_actions:
        cols = st.columns([1,1,1,1])
        if cols[0].button("Voir Détail", key=f"view_{ticket}"):
            navigate_to("Détail", None, ticket)
            st.experimental_rerun()

def page_achats():
    st.markdown("### Espace Achats (Validation et sourcing)")
    # Sub-navigation handled programmatically
    sub = st.radio("Vue Achats", ["Demandes à sourcer", "Demandes validées Achats", "Historique"], index=0 if st.session_state['sub_view'] is None else (["Demandes à sourcer","Demandes validées Achats","Historique"].index(st.session_state['sub_view']) if st.session_state['sub_view'] in ["Demandes à sourcer","Demandes validées Achats","Historique"] else 0))
    st.session_state['sub_view'] = sub
    if sub == "Demandes à sourcer":
        st.markdown("Demandes assignées aux Achats pour sourcing.")
        # list demandes with status Soumis or En attente Achats
        rows = list_demandes()
        actionable = [r for r in rows if r['status'] in ("Soumis", "En attente Achats")]
        if not actionable:
            st.info("Aucune demande à sourcer.")
        for row in actionable:
            render_demande_card(row, show_actions=True)
            if st.button("Ouvrir " + row['ticket_id'], key=f"open_src_{row['ticket_id']}"):
                navigate_to("Détail", "achats", row['ticket_id'])
                st.experimental_rerun()

    elif sub == "Demandes validées Achats":
        st.markdown("Demandes que les Achats ont sourcées et validées (prêtes pour Finance).")
        rows = list_demandes()
        validated = [r for r in rows if r['status'] == "Approuvé Achats"]
        if not validated:
            st.info("Aucune demande validée par les Achats.")
        for row in validated:
            render_demande_card(row, show_actions=True)

    else:  # Historique
        st.markdown("Historique Achats")
        rows = list_demandes()
        for row in rows:
            render_demande_card(row, show_actions=True)

def page_finance():
    st.markdown("### Espace Finance (Contrôles & Vérifications)")
    rows = list_demandes()
    awaiting = [r for r in rows if r['status'] in ("Approuvé Achats", "Soumis", "En attente Finance")]
    if not awaiting:
        st.info("Aucune demande à contrôler.")
    for r in awaiting:
        render_demande_card(r, show_actions=True)
        if st.button("Ouvrir " + r['ticket_id'], key=f"open_fin_{r['ticket_id']}"):
            navigate_to("Détail", "finance", r['ticket_id'])
            st.experimental_rerun()

def page_direction():
    st.markdown("### Tableau Direction Générale — Suivi global")
    st.markdown("La Direction ne validera pas directement : elle a un accès de suivi global et pourra demander un point ou un verrouillage final.")
    rows = list_demandes()
    # DG sees all but cannot change states from here
    for r in rows:
        cols = st.columns([4,1])
        with cols[0]:
            st.markdown(f"**{r['ticket_id']}** — {r['title']}")
            st.markdown(f"- Émetteur: **{r['emitter']}** | Département: **{r['department']}**")
            st.markdown(f"- Statut: **{r['status']}**")
            st.markdown(f"- Motif de refus: {r['motif_refus'] or '—'}")
            st.markdown(f"- Fournisseur retenu: {r['fournisseur_retenu'] or '—'}")
            if r['tags']:
                st.markdown(f"- Étiquettes: {r['tags']}")
            if st.button("Voir la chaîne de vie", key=f"trace_{r['ticket_id']}"):
                # open detail view but DG only read-only
                navigate_to("Détail", "dg_view", r['ticket_id'])
                st.experimental_rerun()

def page_etudes():
    st.markdown("### Études & Cahiers des charges - Historique")
    # For simplicity, use demandes that are "Étude" tagged or all études entries
    rows = list_demandes()
    for r in rows:
        # expanders to read content fully
        with st.expander(f"{r['ticket_id']} — {r['title']}"):
            st.markdown(f"**Émetteur:** {r['emitter']} — **Département:** {r['department']}")
            st.markdown(f"**Description complète:**\n\n{r['description']}")
            if r['tags']:
                st.markdown(f"**Étiquettes:** {r['tags']}")
            st.markdown(f"**Statut:** {r['status']}")
            if st.button("Ouvrir le dossier", key=f"open_etude_{r['ticket_id']}"):
                navigate_to("Détail", "etude", r['ticket_id'])
                st.experimental_rerun()

def page_audit():
    st.markdown("### Audit & Traçabilité")
    tabs = st.tabs(["Journal des actions", "Connexions & Statistiques"])

    # Journal des actions (logs)
    with tabs[0]:
        st.markdown("Journal des actions — qui a fait quoi et quand.")
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM logs_audit ORDER BY created_at DESC LIMIT 500")
        logs = cur.fetchall()
        if not logs:
            st.info("Aucun événement enregistré.")
        else:
            for log in logs:
                st.markdown(f"- [{log['created_at'][:19]}] **{log['ticket_id']}** — {log['action']} par {log['user']} — {log['details']}")
        st.markdown("---")
        st.markdown("Recherche avancée de la chaîne de vie d'un ticket")
        ticket_search = st.text_input("Ticket (#TICK-0001)", value=st.session_state.get('selected_ticket') or "", key='audit_ticket_search')
        if st.button("Afficher la chaîne", key='audit_show'):
            cur.execute("SELECT * FROM logs_audit WHERE ticket_id=? ORDER BY created_at ASC", (ticket_search,))
            rows = cur.fetchall()
            if not rows:
                st.info("Aucun log pour ce ticket.")
            else:
                for r in rows:
                    st.markdown(f"- [{r['created_at'][:19]}] {r['action']} — {r['details']} (par {r['user']})")

    # Connexions & Statistiques (pointage)
    with tabs[1]:
        st.markdown("Suivi des connexions et activité par utilisateur.")
        conn = get_conn()
        cur = conn.cursor()
        # total connections per user
        try:
            cur.execute("SELECT user, COUNT(*) as cnt FROM connections GROUP BY user ORDER BY cnt DESC")
            conn_rows = cur.fetchall()
        except Exception:
            conn_rows = []
        stats = []
        for cr in conn_rows:
            stats.append({"user": cr['user'], "connections_total": cr['cnt']})
        st.table(stats if stats else [])

        # summary KPIs
        conn2 = get_conn()
        cur2 = conn2.cursor()
        cur2.execute("SELECT COUNT(*) as total FROM demandes")
        total_demandes = cur2.fetchone()['total']
        cur2.execute("SELECT status, COUNT(*) as cnt FROM demandes GROUP BY status")
        status_rows = cur2.fetchall()
        conn2.close()
        kpi = {"total_demandes": total_demandes}
        st.markdown(f"- Total demandes: **{total_demandes}**")
        st.markdown("**Par statut:**")
        for s in status_rows:
            st.markdown(f"- {s['status']}: **{s['cnt']}**")

        # Export KPIs / stats to Excel
        if st.button("Exporter les statistiques (Excel)"):
            # build sheets
            sheets = {}
            sheets['Connections'] = stats
            sheets['Demandes_par_statut'] = [{ 'status': r['status'], 'count': r['cnt'] } for r in status_rows]
            sheets['KPI'] = [kpi]
            data_bytes, filename = export_stats_excel(sheets)
            st.download_button("Télécharger les statistiques", data=data_bytes, file_name=filename, mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

def page_detail():
    ticket = st.session_state.get('selected_ticket')
    if not ticket:
        st.info("Aucun ticket sélectionné. Utilisez la boîte de réception ou recherchez un ticket.")
        return
    r = get_demande_by_ticket(ticket)
    if not r:
        st.error("Ticket introuvable.")
        return
    st.header(f"{r['ticket_id']} — {r['title']}")
    st.markdown(f"**Émetteur:** {r['emitter']} — **Département:** {r['department']}")
    st.markdown(f"**Description:**\n\n{r['description']}")
    st.markdown(f"**Étiquettes:** {r['tags'] or '—'}")
    st.markdown(f"**Montant estimé:** {r['estimated_amount'] if r['estimated_amount'] is not None else 'Non renseigné'}")
    st.markdown(f"**Fournisseur pressenti:** {r['fournisseur_pressenti'] or '—'}")
    st.markdown(f"**Fournisseur retenu:** {r['fournisseur_retenu'] or '—'}")
    st.markdown(f"**Statut:** {r['status']}")
    if r['motif_refus']:
        st.markdown(f"**Motif de refus:** {r['motif_refus']}")

    # show audit logs for this ticket
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM logs_audit WHERE ticket_id=? ORDER BY created_at ASC", (ticket,))
    logs = cur.fetchall()
    st.markdown("#### Journal d'activité")
    for l in logs:
        st.markdown(f"- [{l['created_at'][:19]}] **{l['action']}** — {l['details']} (par {l['user']})")

    # Actions depend on role and strict pipeline
    role = st.session_state['current_user']
    if role == "Achats":
        st.markdown("##### Actions Achats")
        with st.form("form_achats_action"):
            # Allow Achats to set final supplier and final amount (they have final say on price)
            fournisseur_retenu = st.text_input("Fournisseur retenu / à confirmer", value=r['fournisseur_retenu'] or r['fournisseur_pressenti'] or "")
            montant_definitif = st.number_input("Montant définitif (Décidé par Achats) - 0 = inchangé", min_value=0.0, step=1.0, value=float(r['estimated_amount']) if r['estimated_amount'] is not None else 0.0)
            action = st.selectbox("Action", ["Sourcer & proposer fournisseur", "Approuver et envoyer à Finance", "Demander modification à l'émetteur", "Refuser (nécessite motif)"])
            motif = st.text_area("Motif (requis si refus)", height=80)
            sub = st.form_submit_button("Valider action Achats")
            if sub:
                # perform strict updates
                # compute amount to save: None if user left 0.0 and original was None
                montant_to_save = None
                try:
                    if montant_definitif and float(montant_definitif) > 0.0:
                        montant_to_save = float(montant_definitif)
                except Exception:
                    montant_to_save = None

                if action == "Refuser (nécessite motif)":
                    if not motif.strip():
                        st.error("Le motif est requis pour un refus.")
                    else:
                        # set status and motif, keep fournisseur if provided
                        update_kwargs = {"status": "Refusé Achats", "motif_refus": motif, "fournisseur_retenu": fournisseur_retenu or None}
                        if montant_to_save is not None:
                            update_kwargs["estimated_amount"] = montant_to_save
                        update_demande(ticket, **update_kwargs)
                        add_log(ticket, role, "Refus Achats", motif)
                        st.success("Demande refusée et motif enregistré.")
                        # notify emitter
                        add_inbox_entry(r['emitter'], ticket, f"Votre demande {ticket} a été refusée par Achats: {motif}", target_tab="Détail", target_sub=None)
                        st.experimental_rerun()
                elif action == "Approuver et envoyer à Finance":
                    # Set fournisseur, final amount if provided, and mark as approved
                    update_kwargs = {"status": "Approuvé Achats", "fournisseur_retenu": fournisseur_retenu or None}
                    if montant_to_save is not None:
                        update_kwargs["estimated_amount"] = montant_to_save
                    update_demande(ticket, **update_kwargs)
                    add_log(ticket, role, "Approuvé Achats", f"Fournisseur retenu: {fournisseur_retenu or '—'} | Montant: {montant_to_save if montant_to_save is not None else '—'}")
                    # Notify Finance via inbox
                    add_inbox_entry("Finance", ticket, f"Demande {ticket} prête pour contrôle financier.", target_tab="Finance", target_sub="en_attente")
                    st.success("Demande approuvée et envoyée à Finance.")
                    st.experimental_rerun()
                elif action == "Demander modification à l'émetteur":
                    update_kwargs = {"status": "Demande Correction - Achats"}
                    if montant_to_save is not None:
                        update_kwargs["estimated_amount"] = montant_to_save
                    if fournisseur_retenu:
                        update_kwargs["fournisseur_retenu"] = fournisseur_retenu
                    update_demande(ticket, **update_kwargs)
                    add_log(ticket, role, "Demande modification", "Soumis retour à l'émetteur pour correction")
                    add_inbox_entry(r['emitter'], ticket, f"Veuillez modifier votre demande {ticket} suite au retour des Achats.", target_tab="Détail")
                    st.success("Demande renvoyée à l'émetteur pour modification.")
                    st.experimental_rerun()
                else:
                    # propose supplier but not finalize
                    update_kwargs = {"fournisseur_retenu": fournisseur_retenu or None}
                    if montant_to_save is not None:
                        update_kwargs["estimated_amount"] = montant_to_save
                    update_demande(ticket, **update_kwargs)
                    add_log(ticket, role, "Proposition fournisseur", f"Proposition: {fournisseur_retenu or '—'} | Montant proposition: {montant_to_save if montant_to_save is not None else '—'}")
                    st.success("Proposition enregistrée (non validée).")
                    st.experimental_rerun()

    elif role == "Finance":
        st.markdown("##### Actions Finance")
        # Finance can approve to move to DG follow (but per spec DG is follow-only)
        with st.form("form_finance_action"):
            action = st.selectbox("Action", ["Effectuer contrôle & approuver vers suivi DG", "Demander correction", "Refuser (motif)"])
            motif = st.text_area("Motif (requis si refus)", height=80)
            sub = st.form_submit_button("Valider action Finance")
            if sub:
                if action == "Refuser (motif)":
                    if not motif.strip():
                        st.error("Motif requis pour refus.")
                    else:
                        update_demande(ticket, status="Refusé Finance", motif_refus=motif)
                        add_log(ticket, role, "Refus Finance", motif)
                        add_inbox_entry(r['emitter'], ticket, f"Votre demande {ticket} a été refusée par Finance: {motif}", target_tab="Détail")
                        st.success("Demande refusée.")
                        st.experimental_rerun()
                elif action == "Demander correction":
                    update_demande(ticket, status="Demande Correction - Finance")
                    add_log(ticket, role, "Demande correction finance", "Retour à l'émetteur")
                    add_inbox_entry(r['emitter'], ticket, f"Veuillez corriger la demande {ticket} suite au contrôle Finance.", target_tab="Détail")
                    st.success("Demande renvoyée à l'émetteur.")
                    st.experimental_rerun()
                else:
                    # Approve and mark as ready for DG follow (but not DG approval)
                    update_demande(ticket, status="Validé Finance - Prêt suivi DG")
                    add_log(ticket, role, "Validé Finance", "Prête pour suivi DG")
                    # Notify DG in inbox but DG won't be able to change status (read-only follow)
                    add_inbox_entry("Direction Générale", ticket, f"Demande {ticket} validée et disponible pour suivi.", target_tab="Direction", target_sub=None)
                    st.success("Demande validée par Finance; DG notifié pour suivi.")
                    st.experimental_rerun()

    elif role == "Direction Générale":
        st.markdown("##### Vue DG (Actions: Suivi, Commentaires & Décisions)")
        st.info("La DG suit la chaîne; elle peut aussi ajouter un point, demander une correction ou refuser une demande si nécessaire.")
        with st.form("form_dg_action"):
            dg_action = st.selectbox("Action DG", ["Commenter", "Demander correction", "Refuser (motif)", "Annuler la demande"]) 
            dg_motif = st.text_area("Motif / commentaire (requis pour refus)")
            dg_submit = st.form_submit_button("Valider action DG")
            if dg_submit:
                if dg_action == "Commenter":
                    if dg_motif.strip():
                        add_log(ticket, role, "Commentaire DG", dg_motif)
                        st.success("Commentaire ajouté au journal.")
                        st.experimental_rerun()
                    else:
                        st.error("Le commentaire ne peut pas être vide.")
                elif dg_action == "Demander correction":
                    update_demande(ticket, status="Demande Correction - DG")
                    add_log(ticket, role, "Demande correction DG", "Retour à l'émetteur pour modification")
                    add_inbox_entry(r['emitter'], ticket, f"La DG demande une modification pour {ticket}.", target_tab="Détail")
                    st.success("Demande renvoyée à l'émetteur pour correction.")
                    st.experimental_rerun()
                elif dg_action == "Refuser (motif)":
                    if not dg_motif.strip():
                        st.error("Motif requis pour un refus.")
                    else:
                        update_demande(ticket, status="Refusé DG", motif_refus=dg_motif)
                        add_log(ticket, role, "Refus DG", dg_motif)
                        add_inbox_entry(r['emitter'], ticket, f"Votre demande {ticket} a été refusée par la Direction Générale: {dg_motif}", target_tab="Détail")
                        st.success("Demande refusée par la DG.")
                        st.experimental_rerun()
                else:
                    # Annuler la demande
                    update_demande(ticket, status="Annulé par DG")
                    add_log(ticket, role, "Annulation DG", "Demande annulée par Direction Générale")
                    add_inbox_entry(r['emitter'], ticket, f"Votre demande {ticket} a été annulée par la Direction Générale.", target_tab="Détail")
                    st.success("Demande annulée.")
                    st.experimental_rerun()

    else:
        # regular user / emitter
        st.markdown("##### Actions émetteur")
        if st.session_state['current_user'] == r['emitter'] or st.session_state['current_user'] == "Admin":
            # Emetteur can update description if in correction statuses
            if r['status'] in ("Demande Correction - Achats", "Demande Correction - Finance", "Demande Correction - DG"):
                with st.form("form_emetteur_correction"):
                    new_desc = st.text_area("Modifier la description", value=r['description'])
                    submit_c = st.form_submit_button("Envoyer modifications")
                    if submit_c:
                        update_demande(ticket, description=new_desc, status="Soumis")
                        add_log(ticket, st.session_state['current_user'], "Modification émetteur", "Description modifiée et resoumise")
                        add_inbox_entry("Achats", ticket, f"Demande {ticket} resoumise après correction.", target_tab="Achats", target_sub="validation_achats")
                        st.success("Modifications envoyées.")
                        st.experimental_rerun()
            # Allow deletion by Admin or emitter
            if st.button("Supprimer la demande (irréversible)"):
                if st.session_state['current_user'] == "Admin" or st.session_state['current_user'] == r['emitter']:
                    delete_demande(ticket)
                    add_log(ticket, st.session_state['current_user'], "Suppression", "Demande supprimée")
                    st.success("Demande supprimée.")
                    st.experimental_rerun()
                else:
                    st.error("Vous n'êtes pas autorisé à supprimer cette demande.")

def page_params():
    st.markdown("### Paramètres & Administration")
    if st.session_state['current_user'] != "Admin":
        st.info("Seul Admin peut gérer ces options.")
    else:
        st.markdown("Purger la base / Débogage")
        if st.button("Réinitialiser compteur tickets (danger)"):
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("UPDATE metadata SET value='0' WHERE key='ticket_counter'")
            conn.commit()
            conn.close()
            st.success("Compteur réinitialisé.")
        if st.button("Purger les inbox_entries (danger)"):
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("DELETE FROM inbox_entries")
            conn.commit()
            conn.close()
            st.success("Inbox vidée.")

# Dispatcher
if st.session_state['main_tab'] == "Accueil":
    page_accueil()
elif st.session_state['main_tab'] == "Soumettre":
    page_soumettre()
elif st.session_state['main_tab'] == "Achats":
    page_achats()
elif st.session_state['main_tab'] == "Finance":
    page_finance()
elif st.session_state['main_tab'] == "Direction":
    page_direction()
elif st.session_state['main_tab'] == "Études":
    page_etudes()
elif st.session_state['main_tab'] == "Audit":
    page_audit()
elif st.session_state['main_tab'] == "Détail":
    page_detail()
elif st.session_state['main_tab'] == "Paramètres":
    page_params()
else:
    st.info("Section inconnue — sélectionnez une section dans la barre latérale.")
