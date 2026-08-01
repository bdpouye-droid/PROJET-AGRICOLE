import os
import sqlite3
import pandas as pd
import streamlit as str_app

# Configuration de base de l'application
DOSSIER_UPLOADS = "uploads"
os.makedirs(DOSSIER_UPLOADS, exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect("projet_agricole.db", timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def get_valeur_globale(cle):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT valeur FROM parametres_globaux WHERE cle = ?", (cle,))
    row = cursor.fetchone()
    conn.close()
    return float(row["valeur"]) if row else 0.0

def set_valeur_globale(cle, valeur):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO parametres_globaux (cle, valeur) VALUES (?, ?)", (cle, str(valeur)))
    conn.commit()
    conn.close()

def ajouter_log(action, acteur, details):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO logs_audit (date, acteur, action, details) VALUES (datetime('now', 'localtime'), ?, ?, ?)", (acteur, action, details))
    conn.commit()
    conn.close()

# Simulation de profil et variables globales pour l'exemple
nom_dept = "Direction"
profil = {"type": "fondateur"}

def afficher_indicateurs_budgetaires_securises():
    str_app.sidebar.title("Pilotage du Projet (96 ha)")
    budget = get_valeur_globale("budget_global")
    solde = get_valeur_globale("solde_restant")
    str_app.sidebar.metric("Budget Global", f"{budget:,.2f} €")
    str_app.sidebar.metric("Trésorerie Disponible", f"{solde:,.2f} €")

def afficher_espace_coordination_et_journal(nom_departement):
    str_app.info(f"Connecté en tant que : {nom_departement}")


# ==========================================
# MODULE EXEMPLE / GESTION DES DEMANDES
# ==========================================
def afficher_module_expression_et_suivi(nom_departement):
    str_app.subheader("📝 Suivi des demandes")
    d_statut = "En attente Achats"
    d_titre = "Achat de matériel"
    d_cc = "Spécifications techniques..."
    d_fourn = "Fournisseur A"
    d_id = 1

    if "modification" in d_statut.lower():
        with str_app.form(f"form_modif_{d_id}", clear_on_submit=True):
            nouv_titre = str_app.text_input("Modifier l'intitulé", value=d_titre)
            nouv_cc = str_app.text_area("Modifier les spécifications", value=d_cc)
            nouv_fourn = str_app.text_input("Modifier le fournisseur", value=d_fourn)
            if str_app.form_submit_button("Soumettre à nouveau la modification"):
                conn_m = get_db_connection()
                cur_m = conn_m.cursor()
                cur_m.execute('''
                    UPDATE demandes 
                    SET titre = ?, cahier_charges = ?, fournisseur = ?, statut = 'En attente Achats', etape_actuelle = 'achats', avis_achats = 'En attente', motif_refus = '' 
                    WHERE id = ?
                ''', (nouv_titre, nouv_cc, nouv_fourn, d_id))
                conn_m.commit()
                conn_m.close()
                ajouter_log("Modification Demande", nom_departement, f"Mise à jour et renvoi de la demande #{d_id}")
                str_app.success("Demande modifiée et renvoyée aux Achats !")
                str_app.rerun()
    else:
        str_app.info("Aucune demande nécessitant une modification pour le moment.")


# ==========================================
# MODULE ACHATS & APPROVISIONNEMENTS
# ==========================================
def afficher_module_achats(nom_departement):
    str_app.subheader("🛒 Traitement des Demandes d'Achat (Sourcing & Chiffrage)")
    
    tab_ach_cours, tab_ach_historique = str_app.tabs(["1. Demandes à Traiter", "2. Historique des Achats"])
    
    with tab_ach_cours:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, cahier_charges, fournisseur, statut, date, fichier_devis FROM demandes WHERE etape_actuelle = 'achats'")
        demandes_achats = cursor.fetchall()
        conn.close()
        
        if demandes_achats:
            for da in demandes_achats:
                da_id, da_dept, da_titre, da_cc, da_fourn, da_statut, da_date, da_fich = da
                with str_app.expander(f"Dossier #{da_id} [{da_dept}] : {da_titre}"):
                    str_app.write(f"**Spécifications :** {da_cc}")
                    str_app.write(f"**Fournisseur suggéré :** {da_fourn}")
                    str_app.write(f"**Date de soumission :** {da_date}")
                    
                    if da_fich:
                        chemin_f = os.path.join(DOSSIER_UPLOADS, da_fich)
                        if os.path.exists(chemin_f):
                            with open(chemin_f, "rb") as file_download:
                                str_app.download_button("📥 Télécharger le devis initial", data=file_download, file_name=da_fich, key=f"dl_achats_{da_id}")
                    
                    with str_app.form(f"form_traitement_achats_{da_id}", clear_on_submit=True):
                        montant_estime = str_app.number_input("Montant chiffré (€)", min_value=0.0, step=100.0, format="%.2f")
                        fournisseur_valide = str_app.text_input("Fournisseur retenu (Sourcing officiel)", value=da_fourn)
                        avis_a = str_app.selectbox("Avis Achats", ["Validé pour Finance", "Refusé / À modifier"])
                        motif = str_app.text_area("Motif (obligatoire en cas de refus / retour)")
                        
                        if str_app.form_submit_button("Valider et transmettre à la Finance"):
                            if avis_a == "Validé pour Finance" and montant_estime > 0:
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute('''
                                    UPDATE demandes 
                                    SET montant = ?, fournisseur = ?, statut = 'En attente Finance', etape_actuelle = 'finance', avis_achats = 'Validé', motif_refus = '' 
                                    WHERE id = ?
                                ''', (montant_estime, fournisseur_valide, da_id))
                                conn.commit()
                                conn.close()
                                ajouter_log("Validation Achats", nom_departement, f"Validation chiffrée ({montant_estime} €) pour la demande #{da_id}")
                                str_app.success("Demande transmise au département Finance !")
                                str_app.rerun()
                            elif avis_a == "Refusé / À modifier" and motif:
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute('''
                                    UPDATE demandes 
                                    SET statut = 'Refusé par Achats (Nécessite modification)', etape_actuelle = 'emetteur', avis_achats = 'Refusé', motif_refus = ? 
                                    WHERE id = ?
                                ''', (motif, da_id))
                                conn.commit()
                                conn.close()
                                ajouter_log("Refus Achats", nom_departement, f"Demande #{da_id} renvoyée pour modification.")
                                str_app.warning("Demande retournée à l'émetteur.")
                                str_app.rerun()
                            else:
                                str_app.error("Veuillez saisir un montant valide et/ou un motif de refus.")
        else:
            str_app.info("Aucune demande d'achat en attente de traitement.")

    with tab_ach_historique:
        str_app.subheader("Historique global des dossiers traités par les Achats")
        conn = get_db_connection()
        df_ach = pd.read_sql_query("SELECT id, departement, titre, montant, fournisseur, statut, date FROM demandes WHERE avis_achats != 'En attente'", conn)
        conn.close()
        if not df_ach.empty:
            str_app.dataframe(df_ach, use_container_width=True)
        else:
            str_app.info("Aucun historique d'achat disponible.")


# ==========================================
# MODULE FINANCE & CONTRÔLE BUDGÉTAIRE
# ==========================================
def afficher_module_finance(nom_departement):
    str_app.subheader("💰 Contrôle Budgétaire & Validation Financière")
    
    budget_g = get_valeur_globale("budget_global")
    solde_r = get_valeur_globale("solde_restant")
    
    col1, col2 = str_app.columns(2)
    col1.metric("Budget Global Actuel", f"{budget_g:,.2f} €")
    col2.metric("Solde Restant Disponible", f"{solde_r:,.2f} €")
    str_app.markdown("---")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, date, fichier_devis FROM demandes WHERE etape_actuelle = 'finance'")
    dossiers_finance = cursor.fetchall()
    conn.close()
    
    if dossiers_finance:
        for df in dossiers_finance:
            df_id, df_dept, df_titre, df_cc, df_montant, df_fourn, df_statut, df_date, df_fich = df
            with str_app.expander(f"Dossier Financement #{df_id} [{df_dept}] : {df_titre} — Montant : {df_montant:,.2f} €"):
                str_app.write(f"**Spécifications :** {df_cc}")
                str_app.write(f"**Fournisseur :** {df_fourn}")
                
                if df_fich:
                    chemin_f = os.path.join(DOSSIER_UPLOADS, df_fich)
                    if os.path.exists(chemin_f):
                        with open(chemin_f, "rb") as file_download:
                            str_app.download_button("📥 Télécharger le devis / justificatif", data=file_download, file_name=df_fich, key=f"dl_fin_{df_id}")
                
                with str_app.form(f"form_finance_{df_id}", clear_on_submit=True):
                    avis_f = str_app.selectbox("Avis Finance", ["Visa Favorable (Transmettre à la Direction)", "Refus Budgétaire / Insuffisance"])
                    motif_f = str_app.text_area("Commentaire ou motif du refus budgétaire")
                    
                    if str_app.form_submit_button("Confirmer la décision financière"):
                        if avis_f.startswith("Visa Favorable"):
                            if df_montant <= solde_r:
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute('''
                                    UPDATE demandes 
                                    SET statut = 'En attente Signature Exécutive', etape_actuelle = 'fondateur', avis_finance = 'Validé', motif_refus = '' 
                                    WHERE id = ?
                                ''', (df_id,))
                                conn.commit()
                                conn.close()
                                ajouter_log("Visa Finance", nom_departement, f"Visa favorable accordé pour la demande #{df_id} ({df_montant} €)")
                                str_app.success("Visa accordé, dossier transmis à la Direction Générale !")
                                str_app.rerun()
                            else:
                                str_app.error("Erreur : Le montant de la demande dépasse le solde budgétaire disponible !")
                        else:
                            if motif_f:
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute('''
                                    UPDATE demandes 
                                    SET statut = 'Refusé par Finance', etape_actuelle = 'emetteur', avis_finance = 'Refusé', motif_refus = ? 
                                    WHERE id = ?
                                ''', (motif_f, df_id))
                                conn.commit()
                                conn.close()
                                ajouter_log("Refus Finance", nom_departement, f"Demande #{df_id} rejetée par la Finance.")
                                str_app.warning("Dossier refusé et retourné à l'émetteur.")
                                str_app.rerun()
                            else:
                                str_app.error("Veuillez indiquer le motif du refus budgétaire.")
    else:
        str_app.info("Aucun dossier en attente de contrôle financier.")


# ==========================================
# MODULE FONDATEUR / DIRECTION GÉNÉRALE
# ==========================================
def afficher_module_fondateur(nom_departement):
    str_app.subheader("👑 Direction Générale — Pilotage Stratégique & Signature Exécutive")
    
    budget_g = get_valeur_globale("budget_global")
    solde_r = get_valeur_globale("solde_restant")
    
    col1, col2, col3 = str_app.columns(3)
    col1.metric("Budget Global Initial", f"{budget_g:,.2f} €")
    col2.metric("Solde Trésorerie Restant", f"{solde_r:,.2f} €")
    col3.metric("Consommation Globale", f"{(budget_g - solde_r):,.2f} € ({((budget_g - solde_r)/budget_g)*100:.1f}%)")
    
    with str_app.expander("⚙️ Paramétrage du Budget Global"):
        with str_app.form("form_param_budget"):
            nouveau_budget = str_app.number_input("Définir le budget global du projet (96 ha)", value=budget_g, step=100000.0, format="%.2f")
            if str_app.form_submit_button("Mettre à jour le budget"):
                set_valeur_globale("budget_global", nouveau_budget)
                if nouveau_budget >= budget_g:
                    diff = nouveau_budget - budget_g
                    set_valeur_globale("solde_restant", solde_r + diff)
                str_app.success("Budget global mis à jour avec succès !")
                str_app.rerun()

    str_app.markdown("---")
    str_app.subheader("📝 Dossiers en attente de Signature Exécutive")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, date, fichier_devis FROM demandes WHERE etape_actuelle = 'fondateur'")
    dossiers_dir = cursor.fetchall()
    conn.close()
    
    if dossiers_dir:
        for dd in dossiers_dir:
            dd_id, dd_dept, dd_titre, dd_cc, dd_montant, dd_fourn, dd_date, dd_fich = dd
            with str_app.expander(f"Signature Requise #{dd_id} [{dd_dept}] : {dd_titre} — Montant : {dd_montant:,.2f} €"):
                str_app.write(f"**Spécifications :** {dd_cc}")
                str_app.write(f"**Fournisseur retenu :** {dd_fourn}")
                
                if dd_fich:
                    chemin_f = os.path.join(DOSSIER_UPLOADS, dd_fich)
                    if os.path.exists(chemin_f):
                        with open(chemin_f, "rb") as file_download:
                            str_app.download_button("📥 Télécharger le devis / justificatif", data=file_download, file_name=dd_fich, key=f"dl_dir_{dd_id}")
                
                col_b1, col_b2 = str_app.columns(2)
                if col_b1.button(f"✍️ Signer et Approuver #{dd_id}", key=f"sign_ok_{dd_id}"):
                    if dd_montant <= solde_r:
                        nouveau_solde = solde_r - dd_montant
                        set_valeur_globale("solde_restant", nouveau_solde)
                        
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE demandes 
                            SET statut = 'Approuvé et Signé', etape_actuelle = 'cloture', motif_refus = '' 
                            WHERE id = ?
                        ''', (dd_id,))
                        conn.commit()
                        conn.close()
                        
                        ajouter_log("Signature Exécutive", nom_departement, f"Approbation et décaissement de {dd_montant} € pour la demande #{dd_id}")
                        str_app.success(f"Dossier #{dd_id} signé et approuvé ! Budget décaissé.")
                        str_app.rerun()
                    else:
                        str_app.error("Fonds insuffisants pour signer ce décaissement.")
                
                if col_b2.button(f"❌ Refuser #{dd_id}", key=f"sign_ko_{dd_id}"):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE demandes 
                        SET statut = 'Refusé par la Direction', etape_actuelle = 'emetteur', motif_refus = 'Refusé par la Direction Générale' 
                        WHERE id = ?
                    ''', (dd_id,))
                    conn.commit()
                    conn.close()
                    ajouter_log("Refus Direction", nom_departement, f"Demande #{dd_id} refusée par la Direction.")
                    str_app.warning("Dossier refusé.")
                    str_app.rerun()
    else:
        str_app.info("Aucun dossier en attente de signature.")

    str_app.markdown("---")
    str_app.subheader("📊 Journaux d'Audit & Traçabilité Complète")
    conn = get_db_connection()
    df_audit = pd.read_sql_query("SELECT id, date, acteur, action, details FROM logs_audit ORDER BY id DESC LIMIT 50", conn)
    conn.close()
    if not df_audit.empty:
        str_app.dataframe(df_audit, use_container_width=True)
    else:
        str_app.info("Aucun log d'audit enregistré.")


# ==========================================
# ROUTING PRINCIPAL & EXECUTION
# ==========================================
afficher_indicateurs_budgetaires_securises()
afficher_espace_coordination_et_journal(nom_dept)
str_app.markdown("---")

if profil["type"] == "achats":
    afficher_module_achats(nom_dept)
elif profil["type"] == "finance":
    afficher_module_finance(nom_dept)
elif profil["type"] == "fondateur":
    afficher_module_fondateur(nom_dept)
else:
    afficher_module_expression_et_suivi(nom_dept)
