import streamlit as str_app
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from io import BytesIO
from fpdf import FPDF
import sqlite3
import json
import os

# --- CONFIGURATION DE LA PAGE ---
str_app.set_page_config(
    page_title="Plateforme de Pilotage - Bureau d'Études",
    page_icon="🏢",
    layout="wide"
)

# --- DOSSIERS POUR LES FICHIERS ET LE LOGO ---
DOSSIER_UPLOADS = "uploads_devis"
if not os.path.exists(DOSSIER_UPLOADS):
    os.makedirs(DOSSIER_UPLOADS)

CHEMIN_LOGO = "logo.png"

# --- STYLE CSS DESIGN & CORPORATE (SaaS Look) ---
str_app.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 150, 255, 0.2);
        border-color: #1f6feb;
    }
    .stTextInput>div>div>input, .stTextArea>div>div>textarea {
        border-radius: 6px;
        border: 1px solid #30363d;
        background-color: #161b22;
        color: #c9d1d9;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.6rem;
        font-weight: 700;
    }
    </style>
""", unsafe_allow_html=True)

# --- ACTUALISATION AUTOMATIQUE ---
st_autorefresh(interval=5000, key="datarefreshcounter")

# --- INITIALISATION DE LA BASE DE DONNÉES SQLITE ---
def init_db():
    conn = sqlite3.connect("database.db", check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_store (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS demandes (
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
            fichier_devis TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cahiers_charges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            departement TEXT,
            titre TEXT,
            contenu TEXT,
            date TEXT,
            destinataires_avis TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages_coordination (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            auteur TEXT,
            texte TEXT,
            date TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS journaux_bord (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            departement TEXT,
            titre TEXT,
            texte TEXT,
            auteur TEXT,
            date TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            acteur TEXT,
            action TEXT,
            details TEXT
        )
    ''')
    
    cursor.execute("SELECT value FROM global_store WHERE key = 'budget_global'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO global_store (key, value) VALUES ('budget_global', ?)", (str(10000000.0),))
        cursor.execute("INSERT INTO global_store (key, value) VALUES ('solde_restant', ?)", (str(10000000.0),))
    
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect("database.db", check_same_thread=False)

def get_valeur_globale(key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM global_store WHERE key = ?", (key,))
    val = cursor.fetchone()
    conn.close()
    return float(val[0]) if val else 0.0

def set_valeur_globale(key, val):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO global_store (key, value) VALUES (?, ?)", (key, str(val)))
    conn.commit()
    conn.close()

def ajouter_log(action, acteur, details):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO logs_audit (date, acteur, action, details) VALUES (?, ?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), acteur, action, details)
    )
    conn.commit()
    conn.close()

# --- DICTIONNAIRE DES UTILISATEURS & RÔLES ---
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
    
    "DEP11": {"nom": "Achats & Approvisionnements", "mdp": "DEP123", "type": "achats", "dept": "Achats & Approvisionnements"},
    "DEP12": {"nom": "Finance & Comptabilité", "mdp": "DEP123", "type": "finance", "dept": "Finance & Comptabilité"},
    "fondateur": {"nom": "Direction Générale - Pilotage Stratégique", "mdp": "mboro2026", "type": "fondateur", "dept": "Direction Générale"}
}

# --- GESTION DE LA CONNEXION ---
if os.path.exists(CHEMIN_LOGO):
    str_app.sidebar.image(CHEMIN_LOGO, use_column_width=True)
else:
    str_app.sidebar.markdown("## 🏢 Bureau d'Études")

str_app.sidebar.markdown("---")

if 'user_connecte' not in str_app.session_state:
    str_app.session_state.user_connecte = None

if str_app.session_state.user_connecte is None:
    str_app.sidebar.subheader("Connexion Collaborateur")
    username = str_app.sidebar.text_input("Identifiant")
    password = str_app.sidebar.text_input("Mot de passe", type="password")
    
    if str_app.sidebar.button("Se connecter"):
        with str_app.spinner("Vérification des accès..."):
            if username in UTILISATEURS and UTILISATEURS[username]["mdp"] == password:
                str_app.session_state.user_connecte = username
                ajouter_log("Connexion", UTILISATEURS[username]["nom"], "Connexion réussie")
                str_app.rerun()
            else:
                str_app.sidebar.error("Identifiant ou mot de passe incorrect.")
    str_app.stop()
else:
    infos_user = UTILISATEURS[str_app.session_state.user_connecte]
    str_app.sidebar.success(f"Connecté en tant que :\n**{infos_user['nom']}**")
    str_app.sidebar.markdown("---")
    
    if str_app.session_state.user_connecte == "fondateur":
        if str_app.sidebar.button("🔄 Réinitialiser l'application (Reset)"):
            with str_app.spinner("Réinitialisation complète..."):
                budget_init = get_valeur_globale("budget_global")
                set_valeur_globale("solde_restant", budget_init)
                
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM demandes")
                cursor.execute("DELETE FROM cahiers_charges")
                cursor.execute("DELETE FROM messages_coordination")
                cursor.execute("DELETE FROM journaux_bord")
                cursor.execute("DELETE FROM logs_audit")
                conn.commit()
                conn.close()
                
                ajouter_log("Réinitialisation", infos_user['nom'], "Base de données remise à zéro")
                str_app.success("Application réinitialisée à zéro !")
                str_app.rerun()
        str_app.sidebar.markdown("---")

    if str_app.sidebar.button("Se déconnecter"):
        with str_app.spinner("Déconnexion sécurisée..."):
            ajouter_log("Déconnexion", infos_user['nom'], "Déconnexion de l'utilisateur")
            str_app.session_state.user_connecte = None
            str_app.rerun()

user_key = str_app.session_state.user_connecte
profil = UTILISATEURS[user_key]
nom_dept = profil["dept"]

str_app.title(f"Tableau de Bord - {profil['nom']}")

# --- NOTIFICATIONS ---
conn_notif = get_db_connection()
cursor_notif = conn_notif.cursor()
if profil["type"] == "achats":
    cursor_notif.execute("SELECT COUNT(*) FROM demandes WHERE etape_actuelle = 'achats' AND avis_achats = 'En attente'")
    nb_pending = cursor_notif.fetchone()[0]
    if nb_pending > 0:
        str_app.warning(f"⚠️ Vous avez **{nb_pending}** demande(s) en attente de chiffrage et de sourcing.")
elif profil["type"] == "finance":
    cursor_notif.execute("SELECT COUNT(*) FROM demandes WHERE etape_actuelle = 'finance' AND avis_finance = 'En attente'")
    nb_pending = cursor_notif.fetchone()[0]
    if nb_pending > 0:
        str_app.warning(f"⚠️ Vous avez **{nb_pending}** dossier(s) en attente de contrôle budgétaire.")
elif profil["type"] == "fondateur":
    cursor_notif.execute("SELECT COUNT(*) FROM demandes WHERE etape_actuelle = 'fondateur'")
    nb_pending = cursor_notif.fetchone()[0]
    if nb_pending > 0:
        str_app.warning(f"⚠️ Vous avez **{nb_pending}** dossier(s) en attente de signature exécutive.")
elif profil["type"] == "standard":
    cursor_notif.execute("SELECT COUNT(*) FROM demandes WHERE departement = ? AND statut LIKE '%Refusé%'", (nom_dept,))
    nb_refus = cursor_notif.fetchone()[0]
    if nb_refus > 0:
        str_app.error(f"❌ Vous avez **{nb_refus}** demande(s) refusée(s) ou nécessitant une modification.")
conn_notif.close()

str_app.markdown("---")

# --- FONCTION PDF ---
def generer_pdf(titre, texte_contenu, infos_complementaires=""):
    pdf = FPDF()
    pdf.add_page()
    
    if os.path.exists(CHEMIN_LOGO):
        try:
            pdf.image(CHEMIN_LOGO, 10, 10, 25)
        except Exception:
            pass
            
    pdf.set_font("Arial", "B", 15)
    pdf.cell(0, 10, txt="BUREAU D'ÉTUDES - DIRECTION GÉNÉRALE", ln=True, align="C")
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 6, txt="Document Officiel de Traçabilité", ln=True, align="C")
    pdf.ln(8)
    pdf.line(10, 32, 200, 32)
    pdf.ln(8)
    
    pdf.set_font("Arial", "B", 13)
    pdf.multi_cell(0, 8, txt=titre, align="L")
    pdf.ln(4)
    
    if infos_complementaires:
        pdf.set_font("Arial", "I", 10)
        pdf.multi_cell(0, 6, txt=infos_complementaires)
        pdf.ln(6)
        
    pdf.set_font("Arial", "", 11)
    pdf.multi_cell(0, 6, txt=texte_contenu)
    
    pdf_bytes = pdf.output(dest='S')
    if isinstance(pdf_bytes, str):
        pdf_bytes = pdf_bytes.encode('latin1', 'replace')
        
    return BytesIO(pdf_bytes)


# ==========================================
# MODULE COLLABORATIF : ESPACE TEAMS & JOURNAL
# ==========================================
def afficher_espace_coordination_et_journal(nom_departement):
    with str_app.expander("💬 **Espace de Coordination Collaboratif (Fil Partagé)**"):
        str_app.markdown("Canal de discussion et de notes transversales entre départements (style flux collaboratif).")
        with str_app.form(f"form_coord_{nom_departement}", clear_on_submit=True):
            texte_msg = str_app.text_input("Publier une note ou un compte-rendu dans le fil")
            submit_msg = str_app.form_submit_button("Envoyer dans le fil")
            if submit_msg and texte_msg:
                with str_app.spinner("Publication..."):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO messages_coordination (auteur, texte, date) VALUES (?, ?, ?)",
                        (nom_departement, texte_msg, datetime.now().strftime("%Y-%m-%d %H:%M"))
                    )
                    conn.commit()
                    conn.close()
                    str_app.rerun()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT auteur, texte, date FROM messages_coordination ORDER BY id DESC")
        messages = cursor.fetchall()
        conn.close()
        
        if messages:
            for m in messages:
                str_app.markdown(f"""
                <div style="background-color: #161b22; padding: 12px; border-radius: 6px; border-left: 3px solid #1f6feb; margin-bottom: 10px;">
                    <small style="color: #8b949e;"><b>{m[0]}</b> — {m[2]}</small><br>
                    <span style="color: #c9d1d9; font-size: 0.95rem;">{m[1]}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            str_app.info("Aucun message dans le fil partagé pour le moment.")

    with str_app.expander(f"📔 **Journal de Bord Personnel ({nom_departement})**"):
        str_app.write("Vos notes internes et suivis quotidiens privés.")
        with str_app.form(f"form_journal_{nom_departement}", clear_on_submit=True):
            titre_j = str_app.text_input("Titre de l'entrée")
            texte_j = str_app.text_area("Notes et avancements")
            submit_j = str_app.form_submit_button("Ajouter au journal")
            
            if submit_j and titre_j and texte_j:
                with str_app.spinner("Enregistrement..."):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO journaux_bord (departement, titre, texte, auteur, date) VALUES (?, ?, ?, ?, ?)",
                        (nom_departement, titre_j, texte_j, nom_departement, datetime.now().strftime("%Y-%m-%d %H:%M"))
                    )
                    conn.commit()
                    conn.close()
                    str_app.success("Entrée enregistrée !")
                    str_app.rerun()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT titre, texte, date FROM journaux_bord WHERE departement = ? ORDER BY id DESC", (nom_departement,))
        journaux = cursor.fetchall()
        conn.close()
        
        if journaux:
            for entree in journaux:
                str_app.markdown(f"**[{entree[2]}] {entree[0]}**\n\n{entree[1]}\n\n---")
        else:
            str_app.info("Aucune entrée dans votre journal de bord.")


# ==========================================
# MODULE CAHIERS DES CHARGES (UNIVERSEL)
# ==========================================
def afficher_module_cahiers_charges(nom_departement):
    str_app.subheader("Cahiers des Charges & Documents Partagés")
    liste_tous_depts = [u["dept"] for u in UTILISATEURS.values() if u["dept"] != nom_departement]

    with str_app.form(f"form_cc_{nom_departement}", clear_on_submit=True):
        titre_doc = str_app.text_input("Intitulé du document")
        contenu_doc = str_app.text_area("Contenu détaillé")
        destinataires_avis = str_app.multiselect("Partager avec pour avis :", liste_tous_depts)
        
        if str_app.form_submit_button("Enregistrer et diffuser"):
            if titre_doc and contenu_doc:
                with str_app.spinner("Enregistrement..."):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO cahiers_charges (departement, titre, contenu, date, destinataires_avis) VALUES (?, ?, ?, ?, ?)",
                        (nom_departement, titre_doc, contenu_doc, datetime.now().strftime("%Y-%m-%d"), json.dumps(destinataires_avis))
                    )
                    conn.commit()
                    conn.close()
                    ajouter_log("Cahier des Charges", nom_departement, f"Création: {titre_doc}")
                    str_app.success("Document enregistré avec succès !")
                    str_app.rerun()
    
    str_app.markdown("### 📁 Mes documents")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, titre, contenu, date, destinataires_avis FROM cahiers_charges WHERE departement = ?", (nom_departement,))
    mes_docs = cursor.fetchall()
    conn.close()
    
    if mes_docs:
        for doc in mes_docs:
            doc_id, doc_titre, doc_contenu, doc_date, doc_dest_json = doc
            destinataires = json.loads(doc_dest_json) if doc_dest_json else []
            partages = ", ".join(destinataires) if destinataires else "Interne"
            
            with str_app.expander(f"Doc #{doc_id} : {doc_titre} (Partagé avec : {partages})"):
                str_app.write(doc_contenu)
                pdf_io = generer_pdf(f"Cahier des Charges\n{doc_titre}", doc_contenu, f"Émetteur: {nom_departement}\nDate: {doc_date}")
                colA, colB = str_app.columns([1,1])
                colA.download_button("📥 Télécharger PDF", data=pdf_io, file_name=f"cc_{doc_id}.pdf", mime="application/pdf", key=f"pdf_{nom_departement}_{doc_id}")
                if colB.button("🗑️ Supprimer", key=f"del_cc_{nom_departement}_{doc_id}"):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM cahiers_charges WHERE id = ?", (doc_id,))
                    conn.commit()
                    conn.close()
                    str_app.rerun()

    str_app.markdown("### 📥 Documents reçus")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, departement, titre, contenu, date, destinataires_avis FROM cahiers_charges WHERE departement != ?", (nom_departement,))
    autres_docs = cursor.fetchall()
    conn.close()
    
    for doc in autres_docs:
        doc_id, d_nom, doc_titre, doc_contenu, doc_date, doc_dest_json = doc
        destinataires = json.loads(doc_dest_json) if doc_dest_json else []
        if nom_departement in destinataires:
            with str_app.expander(f"📬 De [{d_nom}] : {doc_titre}"):
                str_app.write(doc_contenu)
                pdf_recu = generer_pdf(f"{doc_titre}", doc_contenu, f"Émetteur: {d_nom}")
                str_app.download_button("📥 Télécharger PDF", data=pdf_recu, file_name=f"recu_{doc_id}.pdf", mime="application/pdf", key=f"recu_{d_nom}_{doc_id}")


# ==========================================
# MODULE EXPRESSION DE BESOINS & SUIVI
# ==========================================
def afficher_module_expression_et_suivi(nom_departement):
    tab_besoin, tab_suivi = str_app.tabs(["1. Exprimer un Besoin", "2. Suivi de mes Demandes"])
    
    with tab_besoin:
        str_app.subheader("Nouvelle Expression de Besoin")
        with str_app.form("form_expr_besoin", clear_on_submit=True):
            titre_besoin = str_app.text_input("Intitulé de la demande")
            desc_besoin = str_app.text_area("Spécifications techniques / Justificatif")
            fournisseur_suggere = str_app.text_input("Fournisseur pressenti (optionnel)")
            fich_devis = str_app.file_uploader("📥 Joindre un devis/justificatif (PDF, PNG, JPG)", type=["pdf", "png", "jpg", "jpeg"])
            
            if str_app.form_submit_button("Transmettre aux Achats"):
                if titre_besoin and desc_besoin:
                    nom_fichier_sauve = ""
                    if fich_devis is not None:
                        nom_fichier_sauve = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{fich_devis.name}"
                        chemin_complet = os.path.join(DOSSIER_UPLOADS, nom_fichier_sauve)
                        with open(chemin_complet, "wb") as f:
                            f.write(fich_devis.getbuffer())
                    
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        nom_departement, titre_besoin, desc_besoin, 0.0,
                        fournisseur_suggere if fournisseur_suggere else "À sourcer",
                        "En attente Achats", "achats", "En attente", "En attente", "",
                        datetime.now().strftime("%Y-%m-%d %H:%M"), nom_fichier_sauve
                    ))
                    conn.commit()
                    conn.close()
                    ajouter_log("Demande", nom_departement, f"Création: {titre_besoin}")
                    str_app.success("Besoin transmis avec succès !")
                else:
                    str_app.error("Veuillez remplir l'intitulé et les spécifications.")

    with tab_suivi:
        str_app.subheader("Suivi et Gestion des Demandes")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, titre, cahier_charges, fournisseur, statut, motif_refus, fichier_devis FROM demandes WHERE departement = ?", (nom_departement,))
        mes_demandes = cursor.fetchall()
        conn.close()
        
        if mes_demandes:
            for d in mes_demandes:
                d_id, d_titre, d_cc, d_fourn, d_statut, d_motif, d_fich = d
                with str_app.expander(f"Demande #{d_id} : {d_titre} — Statut : {d_statut}"):
                    str_app.write(f"**Spécifications :** {d_cc}")
                    str_app.write(f"**Fournisseur :** {d_fourn}")
                    
                    if d_fich:
                        chemin_f = os.path.join(DOSSIER_UPLOADS, d_fich)
                        if os.path.exists(chemin_f):
                            with open(chemin_f, "rb") as file_download:
                                str_app.download_button("📥 Télécharger le document joint", data=file_download, file_name=d_fich, key=f"dl_fich_{d_id}")
                    
                    if d_motif:
                        str_app.error(f"❌ **Motif du retour / refus :** {d_motif}")
                    
                    if d_statut not in ["Approuvé et Signé", "Annulé par le département"]:
                        if str_app.button(f"🚫 Annuler cette demande #{d_id}", key=f"btn_annuler_{d_id}"):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("UPDATE demandes SET statut = 'Annulé par le département', etape_actuelle = 'annule' WHERE id = ?", (d_id,))
                            conn.commit()
                            conn.close()
                            str_app.success("Demande annulée.")
                            str_app.rerun()

                    if "modification" in d_statut.lower():
                        str_app.info("Modifiez votre demande ci-dessous pour la soumettre à nouveau.")
                        with str_app.form(f"form_modif_{d_id}"):
                            nouveau_titre = str_app.text_input("Modifier l'intitulé", value=d_titre)
                            nouvelles_specs = str_app.text_area("Modifier les spécifications", value=d_cc)
                            nouveau_fournisseur = str_app.text_input("Modifier le fournisseur", value=d_fourn)
                            
                            if str_app.form_submit_button("Resoumettre aux Achats"):
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute('''
                                    UPDATE demandes 
                                    SET titre = ?, cahier_charges = ?, fournisseur = ?, etape_actuelle = 'achats', avis_achats = 'En attente', statut = 'En attente Achats (Modifié)', motif_refus = ''
                                    WHERE id = ?
                                ''', (nouveau_titre, nouvelles_specs, nouveau_fournisseur, d_id))
                                conn.commit()
                                conn.close()
                                str_app.success("Demande mise à jour et relancée !")
                                str_app.rerun()
        else:
            str_app.info("Aucune demande en cours.")


# ==========================================
# TABLEAU DE SUIVI GLOBAL (POUR LES PÔLES DE CONTRÔLE)
# ==========================================
def afficher_suivi_global():
    if profil["type"] in ["achats", "finance", "fondateur"]:
        str_app.markdown("---")
        with str_app.expander("📊 **Tableau de Suivi Global de TOUTES les Demandes**"):
            conn = get_db_connection()
            df_global = pd.read_sql_query("SELECT id, departement, titre, montant, fournisseur, statut, date FROM demandes", conn)
            conn.close()
            if not df_global.empty:
                str_app.dataframe(df_global, use_container_width=True)
            else:
                str_app.info("Aucune demande enregistrée.")


# ==========================================
# ROUTAGE DES INTERFACES SELON LE RÔLE
# ==========================================

budget_global = get_valeur_globale("budget_global")
solde_restant = get_valeur_globale("solde_restant")

# 1. Départements Standards (DEP1 à DEP10)
if profil["type"] == "standard":
    tab1, tab2 = str_app.tabs(["1. Cahiers des Charges", "2. Expressions de Besoins & Suivi"])
    with tab1:
        afficher_module_cahiers_charges(nom_dept)
    with tab2:
        afficher_module_expression_et_suivi(nom_dept)
    str_app.markdown("---")
    afficher_espace_coordination_et_journal(nom_dept)

# 2. Département Achats (DEP11) - SANS budget visible
elif profil["type"] == "achats":
    tab_ach1, tab_ach2, tab_ach3 = str_app.tabs(["1. Chiffrage & Sourcing", "2. Cahiers des Charges", "3. Coordination"])
    
    with tab_ach1:
        str_app.subheader("File d'attente - Achats & Approvisionnements")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, cahier_charges, fournisseur, fichier_devis FROM demandes WHERE etape_actuelle = 'achats' AND avis_achats = 'En attente'")
        demandes_achats = cursor.fetchall()
        conn.close()
        
        if demandes_achats:
            for d in demandes_achats:
                d_id, d_dept, d_titre, d_cc, d_fourn, d_fich = d
                with str_app.expander(f"Besoin #{d_id} - {d_titre} (Émetteur : {d_dept})"):
                    str_app.write(f"**Spécifications :** {d_cc}")
                    str_app.info(f"💡 **Fournisseur suggéré :** {d_fourn}")
                    
                    if d_fich:
                        chemin_f = os.path.join(DOSSIER_UPLOADS, d_fich)
                        if os.path.exists(chemin_f):
                            with open(chemin_f, "rb") as file_download:
                                str_app.download_button("📥 Consulter le devis joint", data=file_download, file_name=d_fich, key=f"dl_ach_{d_id}")
                    
                    with str_app.form(f"form_achats_{d_id}"):
                        fournisseur_choisi = str_app.text_input("Fournisseur retenu", value=d_fourn if d_fourn != "À sourcer" else "")
                        montant_chiffre = str_app.number_input("Montant exact (€)", min_value=0.0, step=100.0)
                        action_achats = str_app.radio("Décision", ["Valider & Transmettre Finance", "Refus définitif (Bloqué)", "Refusé avec demande de modification (vers Émetteur)"], key=f"a_achats_{d_id}")
                        motif = str_app.text_input("Motif obligatoire en cas de refus / modification")
                        
                        if str_app.form_submit_button("Valider la décision"):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            if "Valider" in action_achats and montant_chiffre > 0:
                                cursor.execute("UPDATE demandes SET fournisseur = ?, montant = ?, avis_achats = 'Validé', etape_actuelle = 'finance', statut = 'En attente Finance' WHERE id = ?", (fournisseur_choisi, montant_chiffre, d_id))
                                conn.commit()
                                conn.close()
                                str_app.success("Transmis à la Finance !")
                                str_app.rerun()
                            else:
                                if not motif:
                                    str_app.error("Veuillez saisir un motif.")
                                    conn.close()
                                else:
                                    etape_suivante = "bloque" if "définitif" in action_achats else "modification"
                                    statut_suivi = "Refusé par les Achats" if "définitif" in action_achats else "Refusé avec demande de modification"
                                    cursor.execute("UPDATE demandes SET avis_achats = 'Refusé', motif_refus = ?, etape_actuelle = ?, statut = ? WHERE id = ?", (motif, etape_suivante, statut_suivi, d_id))
                                    conn.commit()
                                    conn.close()
                                    str_app.success("Décision enregistrée.")
                                    str_app.rerun()
        else:
            str_app.info("Aucune demande en attente pour les Achats.")
            
    with tab_ach2:
        afficher_module_cahiers_charges(nom_dept)
    with tab_ach3:
        afficher_espace_coordination_et_journal(nom_dept)

    afficher_suivi_global()

# 3. Département Finance & Comptabilité (DEP12) - AVEC budget et 4 choix
elif profil["type"] == "finance":
    str_app.subheader("Contrôle Budgétaire & Comptabilité")
    col1, col2 = str_app.columns(2)
    col1.metric("Budget Global", f"{budget_global:,.2f} €")
    col2.metric("Solde Restant", f"{solde_restant:,.2f} €")
    
    tab_fin1, tab_fin2, tab_fin3 = str_app.tabs(["1. Contrôle Budgétaire", "2. Cahiers des Charges", "3. Coordination"])
    
    with tab_fin1:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, fichier_devis FROM demandes WHERE etape_actuelle = 'finance' AND avis_finance = 'En attente'")
        demandes_finance = cursor.fetchall()
        conn.close()
        
        if demandes_finance:
            for d in demandes_finance:
                d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_fich = d
                with str_app.expander(f"Dossier #{d_id} - {d_titre} | Montant : {d_montant:,.2f} € (Émetteur : {d_dept})"):
                    str_app.write(f"**Spécifications :** {d_cc}")
                    str_app.write(f"**Fournisseur validé :** {d_fourn}")
                    
                    if d_fich:
                        chemin_f = os.path.join(DOSSIER_UPLOADS, d_fich)
                        if os.path.exists(chemin_f):
                            with open(chemin_f, "rb") as file_download:
                                str_app.download_button("📥 Consulter le devis joint", data=file_download, file_name=d_fich, key=f"dl_fin_{d_id}")
                    
                    with str_app.form(f"form_finance_{d_id}"):
                        action_fin = str_app.radio("Décision Budgétaire", [
                            "1. Valider & Transmettre Direction Générale", 
                            "2. Renvoyer pour modification au Département Émetteur", 
                            "3. Renvoyer pour modification aux Achats", 
                            "4. Refuser définitivement (Blocage budgétaire)"
                        ], key=f"a_fin_{d_id}")
                        motif_fin = str_app.text_input("Motif obligatoire (en cas de modification ou refus)")
                        
                        if str_app.form_submit_button("Valider la décision financière"):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            if "1. Valider" in action_fin:
                                cursor.execute("UPDATE demandes SET avis_finance = 'Validé', etape_actuelle = 'fondateur', statut = 'En attente Signature DG' WHERE id = ?", (d_id,))
                                conn.commit()
                                conn.close()
                                str_app.success("Transmis à la Direction Générale !")
                                str_app.rerun()
                            else:
                                if not motif_fin:
                                    str_app.error("Veuillez saisir un motif.")
                                    conn.close()
                                else:
                                    if "2." in action_fin:
                                        cursor.execute("UPDATE demandes SET avis_finance = 'Modif', motif_refus = ?, etape_actuelle = 'modification', statut = 'Refusé avec demande de modification (Finance)' WHERE id = ?", (motif_fin, d_id))
                                    elif "3." in action_fin:
                                        cursor.execute("UPDATE demandes SET avis_finance = 'Modif Achats', motif_refus = ?, etape_actuelle = 'achats', avis_achats = 'En attente', statut = 'Retour aux Achats (Finance)' WHERE id = ?", (motif_fin, d_id))
                                    else:
                                        cursor.execute("UPDATE demandes SET avis_finance = 'Refusé', motif_refus = ?, etape_actuelle = 'bloque', statut = 'Refusé par la Finance' WHERE id = ?", (motif_fin, d_id))
                                    conn.commit()
                                    conn.close()
                                    str_app.success("Décision financière enregistrée et dossier redirigé.")
                                    str_app.rerun()
        else:
            str_app.info("Aucun dossier en attente de contrôle budgétaire.")
            
    with tab_fin2:
        afficher_module_cahiers_charges(nom_dept)
    with tab_fin3:
        afficher_espace_coordination_et_journal(nom_dept)

    afficher_suivi_global()

# 4. Direction Générale / Pilotage Stratégique (fondateur)
elif profil["type"] == "fondateur":
    str_app.subheader("Direction Générale - Pilotage Stratégique & Signature Exécutive")
    col1, col2 = str_app.columns(2)
    col1.metric("Budget Global Initial", f"{budget_global:,.2f} €")
    col2.metric("Solde Restant Actuel", f"{solde_restant:,.2f} €")
    
    tab_dg1, tab_dg2, tab_dg3, tab_dg4 = str_app.tabs(["1. Signatures Exécutives", "2. Cahiers des Charges", "3. Audit & Traçabilité", "4. Coordination"])
    
    with tab_dg1:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, fichier_devis FROM demandes WHERE etape_actuelle = 'fondateur'")
        dossiers_dg = cursor.fetchall()
        conn.close()
        
        if dossiers_dg:
            for d in dossiers_dg:
                d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_fich = d
                with str_app.expander(f"Dossier Exécutif #{d_id} : {d_titre} — Montant : {d_montant:,.2f} €"):
                    str_app.write(f"**Émetteur :** {d_dept}")
                    str_app.write(f"**Fournisseur :** {d_fourn}")
                    str_app.write(f"**Spécifications :** {d_cc}")
                    
                    if d_fich:
                        chemin_f = os.path.join(DOSSIER_UPLOADS, d_fich)
                        if os.path.exists(chemin_f):
                            with open(chemin_f, "rb") as file_download:
                                str_app.download_button("📥 Télécharger le dossier justificatif", data=file_download, file_name=d_fich, key=f"dl_dg_{d_id}")
                    
                    pdf_contrat = generer_pdf(f"Bon de Commande & Validation DG - #{d_id}", f"Titre: {d_titre}\nMontant: {d_montant} EUR\nFournisseur: {d_fourn}\n\nSpécifications:\n{d_cc}", f"Émetteur: {d_dept}")
                    str_app.download_button("📥 Télécharger PDF Officiel", data=pdf_contrat, file_name=f"contrat_devis_{d_id}.pdf", mime="application/pdf", key=f"pdf_dg_{d_id}")
                    
                    with str_app.form(f"form_dg_{d_id}"):
                        decision_dg = str_app.radio("Validation Exécutive", ["Approuver et Signer (Déduction du solde)", "Rejeter définitivement"], key=f"dec_dg_{d_id}")
                        motif_rejet_dg = str_app.text_input("Motif en cas de rejet")
                        
                        if str_app.form_submit_button("Exécuter la signature"):
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            if "Approuver" in decision_dg:
                                ancien_solde = get_valeur_globale("solde_restant")
                                nouveau_solde = ancien_solde - d_montant
                                set_valeur_globale("solde_restant", nouveau_solde)
                                
                                cursor.execute("UPDATE demandes SET etape_actuelle = 'termine', statut = 'Approuvé et Signé' WHERE id = ?", (d_id,))
                                conn.commit()
                                conn.close()
                                ajouter_log("Signature DG", "Direction Générale", f"Dossier #{d_id} signé pour {d_montant}€")
                                str_app.success("Dossier signé et budget mis à jour !")
                                str_app.rerun()
                            else:
                                if not motif_rejet_dg:
                                    str_app.error("Veuillez saisir un motif de rejet.")
                                    conn.close()
                                else:
                                    cursor.execute("UPDATE demandes SET etape_actuelle = 'bloque', statut = 'Rejeté par la Direction Générale', motif_refus = ? WHERE id = ?", (motif_rejet_dg, d_id))
                                    conn.commit()
                                    conn.close()
                                    ajouter_log("Rejet DG", "Direction Générale", f"Dossier #{d_id} rejeté")
                                    str_app.success("Dossier rejeté.")
                                    str_app.rerun()
        else:
            str_app.info("Aucun dossier en attente de signature exécutive.")
            
    with tab_dg2:
        afficher_module_cahiers_charges(nom_dept)
        
    with tab_dg3:
        str_app.subheader("Journal d'Audit et Traçabilité Complète")
        conn = get_db_connection()
        df_logs = pd.read_sql_query("SELECT * FROM logs_audit ORDER BY id DESC", conn)
        conn.close()
        if not df_logs.empty:
            str_app.dataframe(df_logs, use_container_width=True)
        else:
            str_app.info("Aucun log d'audit enregistré.")
            
    with tab_dg4:
        afficher_espace_coordination_et_journal(nom_dept)

    afficher_suivi_global()
