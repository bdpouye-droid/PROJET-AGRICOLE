import sqlite3
import json
import os
import uuid
import io
from datetime import datetime, date
import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ==========================================
# CONFIGURATION DE LA PAGE
# ==========================================

st.set_page_config(
    page_title="Plateforme de Pilotage - Bureau d'Études",
    page_icon="🏢",
    layout="wide"
)

# ==========================================
# DOSSIERS DE STOCKAGE & CACHE OPTIMISÉ
# ==========================================

DOSSIER_UPLOADS = "uploads_devis"
DOSSIER_ETUDES = "uploads_etudes"
DOSSIER_CDC = "uploads_cdc"
os.makedirs(DOSSIER_UPLOADS, exist_ok=True)
os.makedirs(DOSSIER_ETUDES, exist_ok=True)
os.makedirs(DOSSIER_CDC, exist_ok=True)
CHEMIN_LOGO = "logo.png"

# ==========================================
# STYLE CSS PERSONNALISÉ & DESIGN MODERNE
# ==========================================

st.markdown("""
  <style>
    :root {
      --accent: #5b8def;
      --accent-2: #7c5cf5;
      --bg-card: #151a23;
      --bg-card-2: #11151c;
      --border: #262d3a;
      --text-muted: #8b96a5;
      --success: #2ea043;
      --warning: #d29922;
      --danger: #f85149;
    }
    .stCard {
      background-color: var(--bg-card);
      border: 1px solid var(--border);
      padding: 1rem;
      border-radius: 8px;
      margin-bottom: 0.8rem;
    }
    .pill-valide { background-color: #2ea043; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; }
    .pill-refuse { background-color: #f85149; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; }
    .pill-modif { background-color: #d29922; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; }
    .pill-attente { background-color: #5b8def; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; }
  </style>
""", unsafe_allow_html=True)

# ==========================================
# UTILITAIRES : EXPORT EXCEL / PDF & CACHE
# ==========================================

def _lignes_texte(df: pd.DataFrame):
    lignes = []
    for enregistrement in df.to_dict(orient="records"):
        lignes.append(["" if v is None else str(v) for v in enregistrement.values()])
    return lignes

def exporter_excel_bytes(df: pd.DataFrame, nom_feuille="Données"):
    buffer = io.BytesIO()
    feuille = nom_feuille[:31] or "Données"
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=feuille)
        try:
            worksheet = writer.sheets[feuille]
            lignes = _lignes_texte(df)
            for i, col in enumerate(df.columns):
                try:
                    largeur_contenu = max((len(ligne[i]) for ligne in lignes), default=10) if lignes else 10
                    largeur = min(max(len(str(col)), largeur_contenu) + 2, 50)
                except Exception:
                    largeur = 20
                worksheet.column_dimensions[worksheet.cell(row=1, column=i + 1).column_letter].width = largeur
        except Exception:
            pass
    return buffer.getvalue()

def exporter_pdf_bytes(df: pd.DataFrame, titre="Export", colonnes_max=8):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=1.2 * cm, bottomMargin=1.2 * cm)
    styles = getSampleStyleSheet()
    elements = [Paragraph(titre, styles["Title"]), Spacer(1, 0.4 * cm)]
    elements.append(Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", styles["Normal"]))
    elements.append(Spacer(1, 0.5 * cm))
    
    df_reduit = df.iloc[:, :colonnes_max]
    data = [list(df_reduit.columns)] + _lignes_texte(df_reduit)
    
    t = Table(data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#5b8def')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    elements.append(t)
    doc.build(elements)
    return buffer.getvalue()

def afficher_boutons_export(df: pd.DataFrame, nom_base: str, titre_pdf: str = None, key_prefix: str = ""):
    if df is None or df.empty:
        return
    try:
        excel_bytes = exporter_excel_bytes(df, nom_base)
        pdf_bytes = exporter_pdf_bytes(df, titre_pdf or nom_base)
    except Exception:
        st.caption("⚠️ Export momentanément indisponible pour cette liste.")
        return
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "📊 Exporter en Excel",
            data=excel_bytes,
            file_name=f"{nom_base}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"xlsx_{key_prefix}",
            use_container_width=True
        )
    with c2:
        st.download_button(
            "📄 Exporter en PDF",
            data=pdf_bytes,
            file_name=f"{nom_base}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            key=f"pdf_{key_prefix}",
            use_container_width=True
        )

def pill_statut(statut: str) -> str:
    s = str(statut).lower()
    if "validé" in s or "financé" in s or "approuvé" in s or "signé" in s:
        classe = "pill-valide"
    elif "refusé" in s:
        classe = "pill-refuse"
    elif "modification" in s:
        classe = "pill-modif"
    else:
        classe = "pill-attente"
    return f'<span class="{classe}">{statut}</span>'

def fournisseur_affiche(fournisseur_propose: str, fournisseur_retenu: str) -> str:
    if fournisseur_retenu:
        return f"{fournisseur_retenu} ✅ (retenu par les Achats)"
    elif fournisseur_propose:
        return f"{fournisseur_propose} (pressenti par l'émetteur, non confirmé)"
    return "Non renseigné"

# ==========================================
# INITIALISATION BASE DE DONNÉES
# ==========================================

def init_db():
    conn = sqlite3.connect("database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS global_store (key TEXT PRIMARY KEY, value TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS demandes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        departement TEXT,
        titre TEXT,
        cahier_charges TEXT,
        montant REAL,
        fournisseur TEXT,
        statut TEXT,
        etape_actuelle TEXT,
        avis_achats TEXT,
        avis_finance TEXT,
        motif_refus TEXT,
        date TEXT,
        fichier_devis TEXT,
        retour_remarque TEXT,
        fournisseur_retenu TEXT DEFAULT '',
        archive INTEGER DEFAULT 0
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS etudes_metier (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        departement TEXT,
        titre TEXT,
        donnees_json TEXT,
        fichier_etude TEXT,
        destinataires_partage TEXT,
        date TEXT,
        archive INTEGER DEFAULT 0
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS cahiers_charges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        departement TEXT,
        titre TEXT,
        contenu TEXT,
        date TEXT,
        destinataires_avis TEXT,
        fichier_cdc TEXT DEFAULT '',
        archive INTEGER DEFAULT 0
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS journal_bord (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        departement TEXT,
        auteur TEXT,
        note TEXT,
        date_note TEXT,
        heure_note TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS corbeille_archives (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        departement_auteur TEXT,
        type_element TEXT,
        resume TEXT,
        details_json TEXT,
        date_suppression TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS logs_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        acteur TEXT,
        action TEXT,
        details TEXT
    )''')
    conn.commit()
    conn.close()

def migrer_schema():
    conn = sqlite3.connect("database.db", check_same_thread=False)
    cursor = conn.cursor()
    migrations = [
        ("etudes_metier", "vus_json", "TEXT DEFAULT '[]'"),
        ("cahiers_charges", "vus_par_json", "TEXT DEFAULT '[]'"),
        ("demandes", "fournisseur_retenu", "TEXT DEFAULT ''"),
        ("demandes", "archive", "INTEGER DEFAULT 0"),
        ("etudes_metier", "archive", "INTEGER DEFAULT 0"),
        ("cahiers_charges", "archive", "INTEGER DEFAULT 0"),
        ("cahiers_charges", "fichier_cdc", "TEXT DEFAULT ''"),
    ]
    for table, colonne, type_def in migrations:
        cursor.execute(f"PRAGMA table_info({table})")
        colonnes_existantes = [c[1] for c in cursor.fetchall()]
        if colonne not in colonnes_existantes:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {type_def}")
    conn.commit()
    conn.close()

init_db()
migrer_schema()

def get_db_connection():
    return sqlite3.connect("database.db", check_same_thread=False)

@st.cache_data(ttl=60)
def get_valeur_globale_cached(key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM global_store WHERE key = ?", (key,))
    val = cursor.fetchone()
    conn.close()
    return float(val[0]) if val else 0.0

def get_valeur_globale(key):
    return get_valeur_globale_cached(key)

def set_valeur_globale(key, val):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO global_store (key, value) VALUES (?, ?)", (key, str(val)))
    conn.commit()
    conn.close()
    st.cache_data.clear()

def ajouter_log(action, acteur, details):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO logs_audit (date, acteur, action, details) VALUES (?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), acteur, action, details)
    )
    conn.commit()
    conn.close()

def archiver_dans_corbeille(departement_auteur, type_element, resume, details_dict):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO corbeille_archives (departement_auteur, type_element, resume, details_json, date_suppression) VALUES (?, ?, ?, ?, ?)",
        (departement_auteur, type_element, resume, json.dumps(details_dict), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

def enregistrer_fichier_securise(dossier, fichier):
    if fichier is not None:
        ext = os.path.splitext(fichier.name)[1]
        nom_unique = f"{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
        chemin_complet = os.path.join(dossier, nom_unique)
        with open(chemin_complet, "wb") as f:
            f.write(fichier.getbuffer())
        return nom_unique
    return ""

def proposer_telechargement(dossier, nom_fichier, libelle, key):
    if not nom_fichier:
        return
    try:
        chemin = os.path.join(dossier, nom_fichier)
        if os.path.exists(chemin):
            with open(chemin, "rb") as f:
                st.download_button(libelle, f, file_name=nom_fichier, key=key)
        else:
            st.caption("📎 Pièce jointe indisponible (fichier introuvable).")
    except Exception:
        st.caption("📎 Impossible d'accéder à cette pièce jointe pour le moment.")

# ==========================================
# ROLES ET UTILISATEURS
# ==========================================

UTILISATEURS = {
    "DEP1": {"nom": "Agriculture", "mdp": "DEP123", "type": "standard", "dept": "Agriculture"},
    "DEP2": {"nom": "Élevage & Halieutique", "mdp": "DEP123", "type": "standard", "dept": "Élevage & Halieutique"},
    "DEP3": {"nom": "Industrie & Transformation", "mdp": "DEP123", "type": "standard", "dept": "Industrie & Transformation"},
    "DEP4": {"nom": "Ressources Hydriques", "mdp": "DEP123", "type": "standard", "dept": "Ressources Hydriques"},
    "DEP5": {"nom": "Énergie & Maintenance", "mdp": "DEP123", "type": "standard", "dept": "Énergie & Maintenance"},
    "DEP6": {"nom": "Recherche & Développement", "mdp": "DEP123", "type": "standard", "dept": "Recherche & Développement"},
    "DEP7": {"nom": "Sécurité & HSE", "mdp": "DEP123", "type": "standard", "dept": "Sécurité & HSE"},
    "DEP8": {"nom": "Ressources Humaines & RSE", "mdp": "DEP123", "type": "standard", "dept": "Ressources Humaines & RSE"},
    "DEP9": {"nom": "Commercial & Marketing", "mdp": "DEP123", "type": "standard", "dept": "Commercial & Marketing"},
    "DEP10": {"nom": "IT & Data", "mdp": "DEP123", "type": "standard", "dept": "IT & Data"},
    "DEP11": {"nom": "Logistique", "mdp": "DEP123", "type": "standard", "dept": "Logistique"},
    "DEP12": {"nom": "Achats & Approvisionnements", "mdp": "DEP123", "type": "achats", "dept": "Achats & Approvisionnements"},
    "DEP13": {"nom": "Finance & Comptabilité", "mdp": "DEP123", "type": "finance", "dept": "Finance & Comptabilité"},
    "fondateur": {"nom": "Direction Générale - Pilotage Stratégique", "mdp": "mboro2026", "type": "fondateur", "dept": "Direction Générale"}
}

# ==========================================
# GESTION DE LA SESSION
# ==========================================

if 'user_connecte' not in st.session_state:
    st.session_state.user_connecte = None
if 'tab_actif' not in st.session_state:
    st.session_state.tab_actif = "1. Études & Ingénierie"

# ==========================================
# AUTHENTIFICATION & BARRE LATÉRALE
# ==========================================

if os.path.exists(CHEMIN_LOGO):
    st.sidebar.image(CHEMIN_LOGO, use_container_width=True)
else:
    st.sidebar.markdown("## 🏢 Bureau d'Études")
st.sidebar.markdown("---")

if st.session_state.user_connecte is None:
    st.sidebar.subheader("Connexion Collaborateur")
    username = st.sidebar.text_input("Identifiant")
    password = st.sidebar.text_input("Mot de passe", type="password")
    if st.sidebar.button("Se connecter"):
        if username in UTILISATEURS and UTILISATEURS[username]["mdp"] == password:
            st.session_state.user_connecte = username
            st.session_state.heure_connexion = datetime.now()
            ajouter_log("Connexion", UTILISATEURS[username]["nom"], "Connexion réussie")
            st.toast("Connexion établie avec succès !", icon="✅")
            st.rerun()
        else:
            st.sidebar.error("Identifiant ou mot de passe incorrect.")
    st.stop()

user_key = st.session_state.user_connecte
profil = UTILISATEURS[user_key]
nom_dept = profil["dept"]

st.sidebar.success(f"Connecté : {profil['nom']}")
st.sidebar.markdown("---")

if st.sidebar.button("Se déconnecter"):
    duree = ""
    if "heure_connexion" in st.session_state:
        delta = datetime.now() - st.session_state.heure_connexion
        minutes = int(delta.total_seconds() // 60)
        duree = f"Durée de session : {minutes // 60}h{minutes % 60:02d}min"
    ajouter_log("Déconnexion", profil["nom"], duree or "Durée de session inconnue")
    st.session_state.user_connecte = None
    st.toast("Déconnexion effectuée.", icon="ℹ️")
    st.rerun()

st.title(f"Tableau de Bord - {profil['nom']}")

if profil["type"] in ["finance", "fondateur"]:
    b_total = get_valeur_globale("budget_global")
    b_solde = get_valeur_globale("solde_restant")
    c_b1, c_b2 = st.columns(2)
    c_b1.metric("Budget Global Allocation", f"{b_total:,.2f} €")
    c_b2.metric("Solde Restant Disponible", f"{b_solde:,.2f} €")
    st.markdown("---")

# ==========================================
# NAVIGATION ONGLETS PRINCIPAUX
# ==========================================

onglets_possibles = ["1. Études & Ingénierie", "2. Cahiers des Charges", "3. Besoins & Achats", "📖 Journal de Bord", "🔍 Recherche Globale"]
if profil["type"] in ["achats", "finance", "fondateur"]:
    onglets_possibles.append("📊 Pôle de Contrôle (Suivi Global)")
    onglets_possibles.append("📈 Statistiques")
if profil["type"] == "fondateur":
    onglets_possibles.append("🕵️ Audit & Traçabilité")
    onglets_possibles.append("🗑️ Corbeille & Historique Suppressions")

cols_tabs = st.columns(len(onglets_possibles))
for idx, tab_nom in enumerate(onglets_possibles):
    is_active = (st.session_state.tab_actif == tab_nom)
    btn_type = "primary" if is_active else "secondary"
    if cols_tabs[idx].button(tab_nom, key=f"main_nav_tab_{idx}", use_container_width=True, type=btn_type):
        st.session_state.tab_actif = tab_nom
        st.rerun()

st.markdown("---")

# ==========================================
# 1. MODULE INGÉNIERIE & ÉTUDES MÉTIER
# ==========================================

def afficher_module_etudes(nom_departement, type_profil):
    st.subheader(f"⚙️ Centre d'Ingénierie & Traçabilité des Études — {nom_departement}")
    tous_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]
    t1, t2, t3, t4 = st.tabs(["1. Nouvelle Étude & Partage", "2. Études Reçues", "3. 📜 Historique & Gestion", "4. 🗄️ Archives des Études"])

    with t1:
        with st.form("form_nouvelle_etude", clear_on_submit=True):
            titre = st.text_input("Titre de l'étude / Note technique")
            desc = st.text_area("Description et paramètres")
            destinataires = st.multiselect("Partager cette étude avec d'autres départements", tous_depts)
            fichier = st.file_uploader("Pièce jointe (PDF, Excel, DWG, etc.)", type=["pdf", "xlsx", "docx", "dwg"])
            submitted = st.form_submit_button("Diffuser l'étude")

            if submitted:
                if not titre:
                    st.error("Le titre est obligatoire.")
                else:
                    nom_fichier = enregistrer_fichier_securise(DOSSIER_ETUDES, fichier)
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        """INSERT INTO etudes_metier (departement, titre, donnees_json, fichier_etude, destinataires_partage, date, archive) 
                           VALUES (?, ?, ?, ?, ?, ?, 0)""",
                        (nom_departement, titre, desc, nom_fichier, json.dumps(destinataires), datetime.now().strftime("%Y-%m-%d %H:%M"))
                    )
                    conn.commit()
                    conn.close()
                    ajouter_log("Création Étude", nom_departement, f"Étude: {titre}")
                    st.toast("Étude enregistrée et partagée avec succès !", icon="✅")
                    st.rerun()

    with t2:
        st.markdown("### Études partagées avec votre département")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, donnees_json, fichier_etude, destinataires_partage, date FROM etudes_metier WHERE archive = 0")
        rows = cursor.fetchall()
        conn.close()

        recues = []
        for r in rows:
            dests = json.loads(r[5] if r[5] else "[]")
            if nom_departement in dests or type_profil == "fondateur":
                recues.append(r)

        if not recues:
            st.info("Aucune étude reçue pour le moment.")
        else:
            for r in recues:
                with st.expander(f"📁 [{r[1]}] {r[2]} (Émise le {r[6]})"):
                    st.write(f"**Description & Paramètres :** {r[3]}")
                    proposer_telechargement(DOSSIER_ETUDES, r[4], "📥 Télécharger le document", f"dl_etude_recue_{r[0]}")

    with t3:
        st.markdown("### Vos études émises")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, titre, donnees_json, fichier_etude, date, destinataires_partage FROM etudes_metier WHERE departement = ? AND archive = 0", (nom_departement,))
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            st.info("Vous n'avez publié aucune étude active.")
        else:
            for r in rows:
                eid, etitrans, edesc, efich, edate, edests = r
                with st.expander(f"📄 {etitrans} (le {edate})"):
                    st.write(f"**Description & Paramètres :** {edesc}")
                    st.write(f"**Partagé avec :** {', '.join(json.loads(edests)) if edests else 'Aucun'}")
                    proposer_telechargement(DOSSIER_ETUDES, efich, "📥 Télécharger le document associé", f"dl_etude_emise_{eid}")
                    
                    if st.button("🗄️ Archiver cette étude", key=f"btn_arch_etude_{eid}"):
                        conn_a = get_db_connection()
                        cur_a = conn_a.cursor()
                        cur_a.execute("UPDATE etudes_metier SET archive = 1 WHERE id = ?", (eid,))
                        conn_a.commit()
                        conn_a.close()
                        archiver_dans_corbeille(nom_departement, "Étude Métier", f"Étude : {etitrans}", {"id": eid, "titre": etitrans})
                        ajouter_log("Archivage Étude", nom_departement, f"Étude '{etitrans}' archivée")
                        st.toast("Étude archivée avec succès.", icon="✅")
                        st.rerun()

    with t4:
        st.markdown("### 🗄️ Archives des Études")
        conn = get_db_connection()
        cursor = conn.cursor()
        if type_profil == "fondateur":
            cursor.execute("SELECT id, departement, titre, donnees_json, fichier_etude, date FROM etudes_metier WHERE archive = 1 ORDER BY id DESC")
        else:
            cursor.execute("SELECT id, departement, titre, donnees_json, fichier_etude, date FROM etudes_metier WHERE departement = ? AND archive = 1 ORDER BY id DESC", (nom_departement,))
        archives_etudes = cursor.fetchall()
        conn.close()

        if not archives_etudes:
            st.info("Aucune étude archivée.")
        else:
            for ae in archives_etudes:
                ae_id, ae_dept, ae_titre, ae_desc, ae_fich, ae_date = ae
                with st.expander(f"🗄️ [{ae_dept}] {ae_titre} (Archivée - Émise le {ae_date})"):
                    st.write(f"**Description :** {ae_desc}")
                    proposer_telechargement(DOSSIER_ETUDES, ae_fich, "📥 Télécharger l'étude archivée", f"dl_etude_arch_{ae_id}")


# ==========================================
# 2. MODULE CAHIERS DES CHARGES
# ==========================================

def afficher_module_cdc(nom_departement, type_profil):
    st.subheader("📋 Cahiers des Charges & Documents Partagés")
    tous_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]

    with st.form("form_cdc", clear_on_submit=True):
        titre = st.text_input("Titre du Cahier des Charges")
        contenu = st.text_area("Contenu détaillé / Spécifications techniques")
        destinataires = st.multiselect("Demander un avis / partage aux départements", tous_depts)
        fichier_cdc = st.file_uploader("Pièce jointe du Cahier des Charges (PDF, Word, etc.)", type=["pdf", "docx", "xlsx"])
        submitted = st.form_submit_button("Publier le Cahier des Charges")
        
        if submitted:
            if not titre:
                st.error("Le titre est obligatoire.")
            else:
                nom_fich_cdc = enregistrer_fichier_securise(DOSSIER_CDC, fichier_cdc)
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO cahiers_charges (departement, titre, contenu, date, destinataires_avis, fichier_cdc, archive) 
                       VALUES (?, ?, ?, ?, ?, ?, 0)""",
                    (nom_departement, titre, contenu, datetime.now().strftime("%Y-%m-%d %H:%M"), json.dumps(destinataires), nom_fich_cdc)
                )
                conn.commit()
                conn.close()
                ajouter_log("Création CDC", nom_departement, f"Cahier des charges: {titre}")
                st.toast("Cahier des charges publié avec succès.", icon="✅")
                st.rerun()

    st.markdown("---")
    st.markdown("### 📂 Cahiers des Charges disponibles")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, departement, titre, contenu, date, destinataires_avis, fichier_cdc FROM cahiers_charges WHERE archive = 0")
    rows = cursor.fetchall()
    conn.close()

    for r in rows:
        cid, cdept, ctitre, ccont, cdate, cdests, cfich = r
        with st.expander(f"📋 {ctitre} ({cdept} - {cdate})"):
            st.write(ccont)
            proposer_telechargement(DOSSIER_CDC, cfich, "📥 Télécharger la pièce jointe du CDC", f"dl_cdc_{cid}")


# ==========================================
# 3. MODULE BESOINS & ACHATS (WORKFLOW ADAPTÉ 3 DÉPARTEMENTS PILOTES)
# ==========================================

def afficher_module_achats(nom_departement, type_profil):
    st.subheader("🛒 Gestion des Demandes d'Achat & Workflow de Validation")
    
    # 3 onglets bien distincts comme demandé
    onglets_achats = ["📋 Soumettre une demande", "📊 Suivi des demandes", "🗄️ Archives des demandes"]
    tabs_res = st.tabs(onglets_achats)
    
    with tabs_res[0]:
        st.markdown("### ➕ Soumettre une nouvelle demande d'achat")
        
        if type_profil != "achats" and type_profil != "finance" and type_profil != "fondateur":
            with st.form("form_nouvelle_demande", clear_on_submit=True):
                titre_demande = st.text_input("Intitulé de la demande")
                besoins_specifiques = st.text_area("Besoins spécifiques de la demande")
                cahier_charges_ref = st.text_input("Référence ou lien du Cahier des Charges / Étude associée (optionnel)")
                fournisseur_presenti = st.text_input("Fournisseur pressenti (optionnel)")
                fichier_devis = st.file_uploader("Joindre un devis initial / document descriptif (PDF/Image)", type=["pdf", "png", "jpg", "jpeg"])
                
                soumettre = st.form_submit_button("Soumettre la demande")
                if soumettre:
                    if not titre_demande.strip() or not besoins_specifiques.strip():
                        st.warning("Veuillez renseigner l'intitulé de la demande ainsi que les besoins spécifiques.")
                    else:
                        nom_fichier_devis = enregistrer_fichier_securise(DOSSIER_UPLOADS, fichier_devis)
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            """INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu, archive)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                            (nom_departement, titre_demande, f"Besoin: {besoins_specifiques} | Réf: {cahier_charges_ref}", 0.0, fournisseur_presenti, "En attente Achats", "Achats", "En attente", "En attente", "", datetime.now().strftime("%Y-%m-%d %H:%M"), nom_fichier_devis, "", "", "")
                        )
                        conn.commit()
                        conn.close()
                        ajouter_log("Création Demande d'Achat", nom_departement, f"Demande '{titre_demande}' soumise.")
                        st.toast("✅ Demande transmise aux Achats avec succès !", icon="✅")
                        st.rerun()

        elif type_profil == "achats":
            with st.form("form_nouvelle_demande_achats", clear_on_submit=True):
                titre_demande = st.text_input("Intitulé de la demande")
                besoins_specifiques = st.text_area("Besoins spécifiques de la demande")
                cahier_charges_ref = st.text_input("Référence ou lien associé (optionnel)")
                fournisseur_retenu_saisie = st.text_input("Fournisseur retenu")
                montant_defini = st.number_input("Prix définitif (€)", min_value=0.0, step=10.0)
                fichier_devis = st.file_uploader("Joindre le devis / document justificatif (PDF/Image)", type=["pdf", "png", "jpg", "jpeg"])
                
                soumettre_achats = st.form_submit_button("Soumettre la demande (Circuit direct Finance)")
                if soumettre_achats:
                    if not titre_demande.strip() or not besoins_specifiques.strip():
                        st.warning("Veuillez renseigner l'intitulé et les besoins spécifiques.")
                    else:
                        nom_fichier_devis = enregistrer_fichier_securise(DOSSIER_UPLOADS, fichier_devis)
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            """INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu, archive)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                            (nom_departement, titre_demande, f"Besoin: {besoins_specifiques} | Réf: {cahier_charges_ref}", montant_defini, fournisseur_retenu_saisie, "En attente Finance", "Finance", "Validé", "En attente", "", datetime.now().strftime("%Y-%m-%d %H:%M"), nom_fichier_devis, "", fournisseur_retenu_saisie, "")
                        )
                        conn.commit()
                        conn.close()
                        ajouter_log("Création Demande d'Achat (Achats)", nom_departement, f"Demande '{titre_demande}' transmise directement en Finance.")
                        st.toast("✅ Demande transmise directement à la Finance avec succès !", icon="✅")
                        st.rerun()

        elif type_profil == "finance":
            with st.form("form_nouvelle_demande_finance", clear_on_submit=True):
                titre_demande = st.text_input("Intitulé de la demande")
                besoins_specifiques = st.text_area("Besoins spécifiques de la demande")
                cahier_charges_ref = st.text_input("Référence ou lien associé (optionnel)")
                fournisseur_presenti = st.text_input("Fournisseur pressenti (optionnel)")
                fichier_devis = st.file_uploader("Joindre un devis initial / document (PDF/Image)", type=["pdf", "png", "jpg", "jpeg"])
                
                soumettre_fin = st.form_submit_button("Soumettre la demande (Circuit Achats -> Direction)")
                if soumettre_fin:
                    if not titre_demande.strip() or not besoins_specifiques.strip():
                        st.warning("Veuillez renseigner l'intitulé et les besoins spécifiques.")
                    else:
                        nom_fichier_devis = enregistrer_fichier_securise(DOSSIER_UPLOADS, fichier_devis)
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            """INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu, archive)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                            (nom_departement, titre_demande, f"Besoin: {besoins_specifiques} | Réf: {cahier_charges_ref}", 0.0, fournisseur_presenti, "En attente Achats", "Achats", "En attente", "Validé", "", datetime.now().strftime("%Y-%m-%d %H:%M"), nom_fichier_devis, "", "", "")
                        )
                        conn.commit()
                        conn.close()
                        ajouter_log("Création Demande d'Achat (Finance)", nom_departement, f"Demande '{titre_demande}' transmise aux Achats.")
                        st.toast("✅ Demande transmise aux Achats avec succès !", icon="✅")
                        st.rerun()

        elif type_profil == "fondateur":
            with st.form("form_nouvelle_demande_dir", clear_on_submit=True):
                titre_demande = st.text_input("Intitulé de la demande")
                besoins_specifiques = st.text_area("Besoins spécifiques de la demande")
                cahier_charges_ref = st.text_input("Référence ou lien associé (optionnel)")
                fournisseur_presenti = st.text_input("Fournisseur pressenti (optionnel)")
                fichier_devis = st.file_uploader("Joindre un devis initial / document (PDF/Image)", type=["pdf", "png", "jpg", "jpeg"])
                
                soumettre_dir_emis = st.form_submit_button("Soumettre la demande (Circuit complet Achats -> Finance -> Direction)")
                if soumettre_dir_emis:
                    if not titre_demande.strip() or not besoins_specifiques.strip():
                        st.warning("Veuillez renseigner l'intitulé et les besoins spécifiques.")
                    else:
                        nom_fichier_devis = enregistrer_fichier_securise(DOSSIER_UPLOADS, fichier_devis)
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            """INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu, archive)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                            (nom_departement, titre_demande, f"Besoin: {besoins_specifiques} | Réf: {cahier_charges_ref}", 0.0, fournisseur_presenti, "En attente Achats", "Achats", "En attente", "En attente", "", datetime.now().strftime("%Y-%m-%d %H:%M"), nom_fichier_devis, "", "", "")
                        )
                        conn.commit()
                        conn.close()
                        ajouter_log("Création Demande d'Achat (Direction)", nom_departement, f"Demande '{titre_demande}' transmise aux Achats.")
                        st.toast("✅ Demande transmise aux Achats avec succès !", icon="✅")
                        st.rerun()

    with tabs_res[1]:
        st.markdown("### Suivi de vos demandes & Validations en attente")
        
        # Interface de validation si le profil a des rôles spécifiques
        if type_profil == "achats":
            st.markdown("#### 🛒 Demandes en attente de traitement & Sourcing (Achats)")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu FROM demandes WHERE archive = 0 AND etape_actuelle = 'Achats' ORDER BY id DESC")
            demandes_achats = cursor.fetchall()
            conn.close()

            if demandes_achats:
                for d in demandes_achats:
                    did, d_dept, d_titre, d_cc, d_montant, d_fournisseur, d_statut, d_etape, d_avis_a, d_avis_f, d_motif, d_date, d_fich, d_rem, d_f_retenu = d
                    with st.expander(f"🛒 [{d_dept}] {d_titre}"):
                        st.write(f"**Émetteur** : {d_dept} | **Date** : {d_date}")
                        st.write(f"**Besoins spécifiques & Cahier des charges** : {d_cc}")
                        st.write(f"**Fournisseur pressenti (émetteur)** : {d_fournisseur or 'Aucun'}")
                        proposer_telechargement(DOSSIER_UPLOADS, d_fich, "📎 Télécharger le devis / document initial", f"dl_achats_{did}")
                        
                        with st.form(f"form_traitement_achats_{did}"):
                            fournisseur_retenu_saisie = st.text_input("Définir le fournisseur retenu (Sourcing)", value=d_f_retenu or d_fournisseur)
                            montant_definitif = st.number_input("Saisir le prix définitif négocié (€)", min_value=0.0, step=10.0, value=float(d_montant or 0.0))
                            nouveau_fichier_achat = st.file_uploader("Ajouter / Remplacer le devis achats consolidé (PDF/Image)", type=["pdf", "png", "jpg", "jpeg"], key=f"f_achat_{did}")
                            
                            action_achat = st.selectbox("Décision Achats", ["Valider", "Demander une modification", "Refuser définitivement"])
                            motif_achat = st.text_area("Commentaire / Motif (obligatoire en cas de modification ou refus)")
                            
                            valider_action = st.form_submit_button("Appliquer la décision Achats")
                            if valider_action:
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                fich_u = enregistrer_fichier_securise(DOSSIER_UPLOADS, nouveau_fichier_achat) if nouveau_fichier_achat else d_fich
                                
                                if action_achat == "Valider":
                                    if d_dept == "Finance & Comptabilité":
                                        nouveau_statut = "En attente Direction"
                                        nouvelle_etape = "Direction Générale"
                                    else:
                                        nouveau_statut = "En attente Finance"
                                        nouvelle_etape = "Finance"
                                    avis_a = "Validé"
                                    motif_maj = ""
                                elif action_achat == "Demander une modification":
                                    nouveau_statut = "Modif demandée"
                                    nouvelle_etape = "Émetteur"
                                    avis_a = "Modification demandée"
                                    motif_maj = f"[Achats] {motif_achat}"
                                else:
                                    nouveau_statut = "Refusé"
                                    nouvelle_etape = "Clôturé"
                                    avis_a = "Refusé"
                                    motif_maj = f"[Achats] {motif_achat}"
                                    
                                cursor.execute(
                                    """UPDATE demandes SET fournisseur_retenu = ?, montant = ?, fichier_devis = ?, statut = ?, etape_actuelle = ?, avis_achats = ?, motif_refus = ? WHERE id = ?""",
                                    (fournisseur_retenu_saisie, montant_definitif, fich_u, nouveau_statut, nouvelle_etape, avis_a, motif_maj, did)
                                )
                                conn.commit()
                                conn.close()
                                ajouter_log("Validation Achats", nom_departement, f"Demande {did} traitée : {action_achat}")
                                st.toast("Décision enregistrée avec succès !", icon="✅")
                                st.rerun()

        elif type_profil == "finance":
            st.markdown("#### 💰 Demandes en attente d'analyse budgétaire (Finance)")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu FROM demandes WHERE archive = 0 AND etape_actuelle = 'Finance' ORDER BY id DESC")
            demandes_finance = cursor.fetchall()
            conn.close()

            if demandes_finance:
                for d in demandes_finance:
                    did, d_dept, d_titre, d_cc, d_montant, d_fournisseur, d_statut, d_etape, d_avis_a, d_avis_f, d_motif, d_date, d_fich, d_rem, d_f_retenu = d
                    with st.expander(f"💰 [{d_dept}] {d_titre} — {float(d_montant or 0):,.2f} €"):
                        st.write(f"- **Émetteur** : {d_dept}")
                        st.write(f"- **Description** : {d_cc}")
                        st.write(f"- **Fournisseur retenu (Achats)** : {fournisseur_affiche(d_fournisseur, d_f_retenu)}")
                        st.write(f"- **Prix définitif** : {float(d_montant or 0):,.2f} €")
                        proposer_telechargement(DOSSIER_UPLOADS, d_fich, "📎 Télécharger le devis", f"dl_fin_{did}")
                        
                        with st.form(f"form_traitement_finance_{did}"):
                            action_fin = st.selectbox("Décision Finance", ["Valider", "Demander une modification", "Refuser (problème budgétaire)"])
                            motif_fin = st.text_area("Commentaire / Motif financier")
                            
                            valider_fin = st.form_submit_button("Appliquer la décision financière")
                            if valider_fin:
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                if action_fin == "Valider":
                                    nouveau_statut = "En attente Direction"
                                    nouvelle_etape = "Direction Générale"
                                    avis_f = "Validé"
                                    motif_maj = ""
                                elif action_fin == "Demander une modification":
                                    nouveau_statut = "Modif demandée"
                                    nouvelle_etape = "Émetteur"
                                    avis_f = "Modification demandée"
                                    motif_maj = f"[Finance] {motif_fin}"
                                else:
                                    nouveau_statut = "Refusé"
                                    nouvelle_etape = "Clôturé"
                                    avis_f = "Refusé"
                                    motif_maj = f"[Finance] {motif_fin}"
                                    
                                cursor.execute(
                                    """UPDATE demandes SET statut = ?, etape_actuelle = ?, avis_finance = ?, motif_refus = ? WHERE id = ?""",
                                    (nouveau_statut, nouvelle_etape, avis_f, motif_maj, did)
                                )
                                conn.commit()
                                conn.close()
                                ajouter_log("Validation Finance", nom_departement, f"Demande {did} traitée : {action_fin}")
                                st.toast("Décision financière enregistrée !", icon="✅")
                                st.rerun()

        elif type_profil == "fondateur":
            st.markdown("#### ✍️ Demandes en attente de validation finale (Direction Générale)")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu FROM demandes WHERE archive = 0 AND etape_actuelle = 'Direction Générale' ORDER BY id DESC")
            demandes_dir = cursor.fetchall()
            conn.close()

            if demandes_dir:
                for d in demandes_dir:
                    did, d_dept, d_titre, d_cc, d_montant, d_fournisseur, d_statut, d_etape, d_avis_a, d_avis_f, d_motif, d_date, d_fich, d_rem, d_f_retenu = d
                    with st.expander(f"✍️ [{d_dept}] {d_titre} — {float(d_montant or 0):,.2f} €"):
                        st.write(f"- **Émetteur** : {d_dept}")
                        st.write(f"- **Description** : {d_cc}")
                        st.write(f"- **Fournisseur retenu** : {fournisseur_affiche(d_fournisseur, d_f_retenu)}")
                        st.write(f"- **Montant** : {float(d_montant or 0):,.2f} €")
                        proposer_telechargement(DOSSIER_UPLOADS, d_fich, "📎 Télécharger le dossier", f"dl_dir_{did}")
                        
                        with st.form(f"form_traitement_dir_{did}"):
                            action_dir = st.selectbox("Décision Direction Générale", ["Valider et signer (Exécution finale)", "Demander une modification", "Refuser définitivement"])
                            motif_dir = st.text_area("Commentaire / Motif de la Direction")
                            
                            valider_dir = st.form_submit_button("Appliquer la décision finale")
                            if valider_dir:
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                if action_dir == "Valider et signer (Exécution finale)":
                                    nouveau_statut = "Validé & Signé"
                                    nouvelle_etape = "Clôturé"
                                    motif_maj = ""
                                    solde_actuel = get_valeur_globale("solde_restant")
                                    montant_dem = float(d_montant or 0)
                                    set_valeur_globale("solde_restant", max(0.0, solde_actuel - montant_dem))
                                elif action_dir == "Demander une modification":
                                    nouveau_statut = "Modif demandée"
                                    nouvelle_etape = "Émetteur"
                                    motif_maj = f"[Direction] {motif_dir}"
                                else:
                                    nouveau_statut = "Refusé"
                                    nouvelle_etape = "Clôturé"
                                    motif_maj = f"[Direction] {motif_dir}"
                                    
                                cursor.execute(
                                    """UPDATE demandes SET statut = ?, etape_actuelle = ?, motif_refus = ? WHERE id = ?""",
                                    (nouveau_statut, nouvelle_etape, motif_maj, did)
                                )
                                conn.commit()
                                conn.close()
                                ajouter_log("Validation Direction Générale", nom_departement, f"Demande {did} traitée : {action_dir}")
                                st.toast("Décision finale enregistrée avec succès !", icon="✅")
                                st.rerun()

        # Affichage des demandes propres au département ou global pour le fondateur
        conn = get_db_connection()
        cursor = conn.cursor()
        if type_profil == "fondateur":
            cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu FROM demandes WHERE archive = 0 ORDER BY id DESC")
        else:
            cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu FROM demandes WHERE departement = ? AND archive = 0 ORDER BY id DESC", (nom_departement,))
        demandes = cursor.fetchall()
        conn.close()

        if not demandes:
            st.info("Aucune demande active en cours.")
        else:
            for d in demandes:
                did, d_dept, d_titre, d_cc, d_montant, d_fournisseur, d_statut, d_etape, d_avis_a, d_avis_f, d_motif, d_date, d_fich, d_rem, d_f_retenu = d
                try:
                    montant_aff = float(d_montant) if d_montant is not None else 0.0
                except (ValueError, TypeError):
                    montant_aff = 0.0

                with st.container():
                    st.markdown(f"""
                        <div class="stCard">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div><b>[{d_dept}] {d_titre}</b> (Étape actuelle : <i>{d_etape}</i>)</div>
                                <div>{pill_statut(d_statut)}</div>
                            </div>
                            <div style="color: var(--text-muted); font-size: 0.9rem; margin-top: 5px;">
                                Montant validé : <b>{montant_aff:,.2f} €</b> | Date : {d_date}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    c_det, c_arch = st.columns([4, 1])
                    with c_det:
                        with st.expander("🔍 Voir les détails complets & historique"):
                            st.write(f"- **Besoins spécifiques** : {d_cc}")
                            st.write(f"- **Fournisseur** : {fournisseur_affiche(d_fournisseur, d_f_retenu)}")
                            st.write(f"- **Avis Achats** : {d_avis_a} | **Avis Finance** : {d_avis_f}")
                            if d_motif:
                                st.warning(f"Motif / Remarque : {d_motif}")
                            proposer_telechargement(DOSSIER_UPLOADS, d_fich, "📎 Télécharger le devis", f"dl_devis_{did}")
                            
                            if d_statut == "Modif demandée" and d_dept == nom_departement:
                                st.markdown("---")
                                st.info("🔄 Cette demande nécessite une modification suite à un retour.")
                                with st.form(f"form_modif_demandeur_{did}"):
                                    nouveau_titre = st.text_input("Modifier l'intitulé", value=d_titre)
                                    nouveaux_besoins = st.text_area("Modifier les besoins spécifiques", value=d_cc)
                                    nouveau_fichier = st.file_uploader("Remplacer le document / devis", type=["pdf", "png", "jpg", "jpeg"], key=f"file_mod_{did}")
                                    resoumettre = st.form_submit_button("Modifier et resoumettre")
                                    if resoumettre:
                                        fich_final = enregistrer_fichier_securise(DOSSIER_UPLOADS, nouveau_fichier) if nouveau_fichier else d_fich
                                        if d_dept == "Achats & Approvisionnements":
                                            prochaine_etape = "Finance"
                                            nouveau_statut_res = "En attente Finance"
                                        else:
                                            prochaine_etape = "Achats"
                                            nouveau_statut_res = "En attente Achats"

                                        conn_m = get_db_connection()
                                        cur_m = conn_m.cursor()
                                        cur_m.execute(
                                            """UPDATE demandes SET titre = ?, cahier_charges = ?, statut = ?, etape_actuelle = ?, motif_refus = ?, fichier_devis = ? WHERE id = ?""",
                                            (nouveau_titre, nouveaux_besoins, nouveau_statut_res, prochaine_etape, "", fich_final, did)
                                        )
                                        conn_m.commit()
                                        conn_m.close()
                                        ajouter_log("Resoumission Demande", nom_departement, f"Demande {did} modifiée et resoumise.")
                                        st.toast("Demande modifiée et transmise avec succès !", icon="✅")
                                        st.rerun()

                    with c_arch:
                        if st.button("🗄️ Archiver", key=f"btn_archiver_{did}", use_container_width=True):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("UPDATE demandes SET archive = 1 WHERE id = ?", (did,))
                            conn.commit()
                            conn.close()
                            archiver_dans_corbeille(nom_departement, "Demande d'Achat", f"Demande : {d_titre}", {"id": did, "titre": d_titre, "montant": montant_aff})
                            ajouter_log("Archivage Demande", nom_departement, f"Demande '{d_titre}' archivée")
                            st.toast("Demande archivée avec succès.", icon="✅")
                            st.rerun()

    with tabs_res[2]:
        st.markdown("### 🗄️ Archives des demandes d'achat")
        conn = get_db_connection()
        cursor = conn.cursor()
        if type_profil == "fondateur":
            cursor.execute("SELECT id, departement, titre, montant, statut, date FROM demandes WHERE archive = 1 ORDER BY id DESC")
        else:
            cursor.execute("SELECT id, departement, titre, montant, statut, date FROM demandes WHERE departement = ? AND archive = 1 ORDER BY id DESC", (nom_departement,))
        archives = cursor.fetchall()
        conn.close()

        if not archives:
            st.info("Aucune demande archivée.")
        else:
            df_arch = pd.DataFrame(archives, columns=["ID", "Département", "Titre", "Montant (€)", "Statut", "Date"])
            st.dataframe(df_arch, use_container_width=True)
            afficher_boutons_export(df_arch, "archives_demandes", "Archives des Demandes d'Achat", "arch_dem")


# ==========================================
# 4. JOURNAL DE BORD QUOTIDIEN
# ==========================================

def afficher_module_journal_bord(nom_departement):
    st.subheader(f"📖 Journal de Bord Quotidien & Cahier de Notes — {nom_departement}")
    with st.form("form_journal", clear_on_submit=True):
        note = st.text_area("Note / Événement marquant du jour")
        submitted = st.form_submit_button("Enregistrer dans le journal")
        if submitted and note:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO journal_bord (departement, auteur, note, date_note, heure_note) 
                   VALUES (?, ?, ?, ?, ?)""",
                (nom_departement, profil["nom"], note, date.today().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M"))
            )
            conn.commit()
            conn.close()
            st.toast("Note ajoutée au journal.", icon="✅")
            st.rerun()

    st.markdown("---")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, auteur, note, date_note, heure_note FROM journal_bord WHERE departement = ? ORDER BY id DESC", (nom_departement,))
    rows = cursor.fetchall()
    conn.close()

    for r in rows:
        with st.container(border=True):
            st.markdown(f"**{r[1]}** — *{r[3]} à {r[4]}*")
            st.write(r[2])


# ==========================================
# 5. MODULE SUIVI GLOBAL POUR PÔLE DE CONTRÔLE
# ==========================================

def afficher_module_suivi_global_controle():
    st.subheader("📊 Pôle de Contrôle & Supervision Globale")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, departement, titre, montant, statut, etape_actuelle, date FROM demandes")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        st.info("Aucune donnée de suivi global.")
        return

    df_suivi = pd.DataFrame(rows, columns=["ID", "Département", "Titre", "Montant", "Statut", "Étape Actuelle", "Date"])
    st.dataframe(df_suivi, use_container_width=True)
    afficher_boutons_export(df_suivi, "Suivi_Global_Controle", "Supervision Globale")


# ==========================================
# 6. MODULE CORBEILLE & HISTORIQUE
# ==========================================

def afficher_module_direction_corbeille():
    st.subheader("🗑️ Supervisions des Éléments Supprimés (Corbeille Centralisée)")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, departement_auteur, type_element, resume, date_suppression FROM corbeille_archives")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        st.success("La corbeille est vide.")
    else:
        df_corb = pd.DataFrame(rows, columns=["ID", "Département Auteur", "Type", "Résumé", "Date Suppression"])
        st.dataframe(df_corb, use_container_width=True)
        afficher_boutons_export(df_corb, "Corbeille_Archives", "Historique des Suppressions")


# ==========================================
# 7. MODULE AUDIT & TRAÇABILITÉ (AVEC BOUTON DE REMISE À ZÉRO RÉSERVÉ AU FONDATEUR)
# ==========================================

def afficher_module_audit():
    st.subheader("🕵️ Audit & Traçabilité (Connexions, Durées & Actions)")
    
    if profil["type"] == "fondateur":
        with st.container(border=True):
            st.markdown("### ⚠️ Zone de Réinitialisation Globale (Crash-Test)")
            st.markdown("Ce bouton permet de remettre l'ensemble des données de l'application à zéro (demandes, études, cahiers des charges, journaux, corbeille, logs) et de réinitialiser le budget global.")
            
            confirmation_reset = st.checkbox("Je confirme vouloir tout effacer et réinitialiser l'application")
            if st.button("🗑️ Réinitialiser toutes les données (Remise à zéro)", type="primary"):
                if confirmation_reset:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM demandes")
                    cursor.execute("DELETE FROM etudes_metier")
                    cursor.execute("DELETE FROM cahiers_charges")
                    cursor.execute("DELETE FROM journal_bord")
                    cursor.execute("DELETE FROM corbeille_archives")
                    cursor.execute("DELETE FROM logs_audit")
                    conn.commit()
                    conn.close()
                    set_valeur_globale("budget_global", 100000.0)
                    set_valeur_globale("solde_restant", 100000.0)
                    ajouter_log("Réinitialisation Système", profil["nom"], "Remise à zéro complète effectuée pour crash-test.")
                    st.toast("Application réinitialisée à zéro avec succès !", icon="✅")
                    st.rerun()
                else:
                    st.warning("Veuillez cocher la case de confirmation pour exécuter la réinitialisation.")
        st.markdown("---")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, date, acteur, action, details FROM logs_audit ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        st.info("Aucun journal d'audit disponible.")
    else:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtre_acteur = st.text_input("Filtrer par acteur / utilisateur")
        with col_f2:
            filtre_action = st.selectbox("Filtrer par type d'action", ["Tous", "Connexion", "Déconnexion", "Validation", "Création", "Réinitialisation"])

        logs_filtres = []
        for r in rows:
            _, r_date, r_acteur, r_action, r_details = r
            if filtre_acteur and filtre_acteur.lower() not in r_acteur.lower():
                continue
            if filtre_action != "Tous" and filtre_action.lower() not in r_action.lower():
                continue
            logs_filtres.append(r)

        if not logs_filtres:
            st.warning("Aucun journal ne correspond aux filtres sélectionnés.")
        else:
            for r in logs_filtres:
                r_id, r_date, r_acteur, r_action, r_details = r
                badge_color = "var(--accent)"
                if "connexion" in r_action.lower():
                    badge_color = "var(--success)"
                elif "déconnexion" in r_action.lower():
                    badge_color = "var(--danger)"
                elif "validation" in r_action.lower():
                    badge_color = "var(--warning)"
                elif "réinitialisation" in r_action.lower():
                    badge_color = "var(--danger)"

                st.markdown(f"""
                    <div class="stCard" style="border-left: 4px solid {badge_color};">
                        <div style="display: flex; justify-content: space-between; font-weight: bold;">
                            <span>👤 {r_acteur}</span>
                            <span style="color: var(--text-muted); font-size: 0.85rem;">🕒 {r_date}</span>
                        </div>
                        <div style="margin-top: 6px;">
                            <span style="background-color: {badge_color}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;">{r_action}</span>
                            <span style="margin-left: 8px; font-size: 0.95rem;">{r_details}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

        st.markdown("---")
        df_audit = pd.DataFrame(rows, columns=["ID", "Date", "Acteur", "Action", "Détails"])
        afficher_boutons_export(df_audit, "Logs_Audit", "Journal d'Audit", "audit_exp")


# ==========================================
# 8. MODULE RECHERCHE GLOBALE
# ==========================================

def afficher_module_recherche_globale(nom_departement, type_profil):
    st.subheader("🔍 Recherche Globale")
    terme = st.text_input("Mot-clé à rechercher dans les études, demandes, statuts ou départements")
    if terme:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT titre, departement, 'Étude' FROM etudes_metier WHERE titre LIKE ? OR donnees_json LIKE ? OR departement LIKE ?", (f"%{terme}%", f"%{terme}%", f"%{terme}%"))
        res_etudes = cursor.fetchall()
        cursor.execute("SELECT titre, departement, 'Demande Achat' FROM demandes WHERE titre LIKE ? OR cahier_charges LIKE ? OR statut LIKE ? OR departement LIKE ?", (f"%{terme}%", f"%{terme}%", f"%{terme}%", f"%{terme}%"))
        res_demandes = cursor.fetchall()
        conn.close()

        tous_res = res_etudes + res_demandes
        if not tous_res:
            st.warning("Aucun résultat trouvé.")
        else:
            for r in tous_res:
                st.write(f"- **[{r[2]}]** {r[0]} *(Émis par {r[1]})*")


# ==========================================
# 9. MODULE STATISTIQUES
# ==========================================

def afficher_module_statistiques():
    st.subheader("📈 Statistiques par Département")
    conn = get_db_connection()
    df_dem = pd.read_sql_query("SELECT departement, montant FROM demandes", conn)
    conn.close()

    if df_dem.empty:
        st.info("Pas assez de données pour afficher les statistiques.")
    else:
        df_dem['montant'] = pd.to_numeric(df_dem['montant'], errors='coerce').fillna(0)
        df_stats = df_dem.groupby("departement").sum().reset_index()
        st.bar_chart(df_stats, x="departement", y="montant")


# ==========================================
# ROUTAGE DYNAMIQUE DES VUES
# ==========================================

if st.session_state.tab_actif == "1. Études & Ingénierie":
    afficher_module_etudes(nom_dept, profil["type"])
elif st.session_state.tab_actif == "2. Cahiers des Charges":
    afficher_module_cdc(nom_dept, profil["type"])
elif st.session_state.tab_actif == "3. Besoins & Achats":
    afficher_module_achats(nom_dept, profil["type"])
elif st.session_state.tab_actif == "📖 Journal de Bord":
    afficher_module_journal_bord(nom_dept)
elif st.session_state.tab_actif == "📊 Pôle de Contrôle (Suivi Global)":
    afficher_module_suivi_global_controle()
elif st.session_state.tab_actif == "🔍 Recherche Globale":
    afficher_module_recherche_globale(nom_dept, profil["type"])
elif st.session_state.tab_actif == "📈 Statistiques":
    afficher_module_statistiques()
elif st.session_state.tab_actif == "🕵️ Audit & Traçabilité":
    afficher_module_audit()
elif st.session_state.tab_actif == "🗑️ Corbeille & Historique Suppressions":
    afficher_module_direction_corbeille()
