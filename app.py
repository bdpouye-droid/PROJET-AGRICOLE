expander_title = f"📋 [{c_dept}] {c_titre} ({c_date})"
                if nom_departement in dests and nom_departement not in avis_dict:
                    expander_title += " ⚠️ [Avis requis]"
                with st.expander(expander_title):
                    st.write(f"**Contenu :**\n{c_contenu}")
                    st.markdown("---")
                    st.write("**Avis recueillis :**")
                    if avis_dict:
                        for d_nom, avi_txt in avis_dict.items():
                            st.write(f"- **{d_nom}** : {avi_txt}")
                    else:
                        st.info("Aucun avis émis pour le moment.")
                    
                    if nom_departement in dests:
                        with st.form(f"form_avis_{c_id}_{nom_departement}"):
                            mon_avis = st.text_area("Votre avis / remarque technique", value=avis_dict.get(nom_departement, ""))
                            if st.form_submit_button("Soumettre mon avis"):
                                avis_dict[nom_departement] = mon_avis
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute("UPDATE cahiers_charges SET avis_recueillis = ? WHERE id = ?", (json.dumps(avis_dict), c_id))
                                conn.commit()
                                conn.close()
                                ajouter_log("Avis CDC", nom_departement, f"Avis donné sur CDC ID {c_id}")
                                add_notification(c_dept, None, f"Avis de {nom_departement} sur votre CDC: {c_titre}", target_tab="2. Cahiers des Charges")
                                st.success("Avis enregistré avec succès !")
                                st.rerun()
                    
                    if nom_departement == c_dept or type_profil == "fondateur":
                        if st.button("🗑️ Supprimer ce CDC", key=f"del_cdc_{c_id}"):
                            archiver_dans_corbeille(c_dept, "Cahier des Charges", c_titre, {"contenu": c_contenu, "date": c_date})
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM cahiers_charges WHERE id = ?", (c_id,))
                            conn.commit()
                            conn.close()
                            ajouter_log("Suppression CDC", c_dept, f"CDC supprimé : {c_titre}")
                            st.success("Cahier des charges supprimé et archivé.")
                            st.rerun()
        else:
            st.info("Aucun cahier des charges disponible.")

# ---------- Module Besoins & Achats ----------
def afficher_module_achats(nom_departement, type_profil):
    st.subheader(f"🛒 Gestion des Besoins, Demandes d'Achat & Workflow — {nom_departement}")
    
    # Gestion du ticket sélectionné depuis la sidebar ou la navigation globale
    selected_ticket = st.session_state.get('selected_ticket', None)
    
    t1, t2 = st.tabs(["1. Nouvelle Demande d'Achat", "2. Suivi & Validation des Demandes"])
    with t1:
        if type_profil in ["achats", "finance", "fondateur"]:
            st.info("Les départements Achats, Finance et Direction Générale pilotent et valident les demandes. Créez une demande depuis votre propre département opérationnel si nécessaire.")
        else:
            with st.form(f"form_achat_{nom_departement}", clear_on_submit=True):
                titre = st.text_input("Intitulé du besoin / Achat")
                cahier_charges = st.text_area("Justification et spécifications techniques")
                montant = st.number_input("Montant estimé (€)", min_value=0.0, step=100.0)
                fournisseur = st.text_input("Fournisseur pressenti (optionnel)")
                fich_devis = st.file_uploader("📥 Joindre un devis / proforma", type=["pdf", "png", "jpg", "xlsx"])
                
                if st.form_submit_button("🚀 Soumettre la Demande d'Achat") and titre:
                    nom_f = enregistrer_fichier_securise(DOSSIER_UPLOADS, fich_devis)
                    
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE metadata SET value = CAST(value AS INTEGER) + 1 WHERE key = 'ticket_counter'")
                    cursor.execute("SELECT value FROM metadata WHERE key = 'ticket_counter'")
                    counter_row = cursor.fetchone()
                    ticket_num = f"#TICK-{int(counter_row[0]):04d}" if counter_row else f"#TICK-{uuid.uuid4().hex[:4].upper()}"
                    
                    cursor.execute("""
                        INSERT INTO demandes (departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu, numero_ticket)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        nom_departement, titre, cahier_charges, montant, fournisseur,
                        "En attente (Achats)", "Achats", "En attente", "En attente", "",
                        datetime.now().strftime("%Y-%m-%d %H:%M"), nom_f, "", "", ticket_num
                    ))
                    conn.commit()
                    conn.close()
                    
                    ajouter_log("Demande d'Achat", nom_departement, f"Demande créée {ticket_num} : {titre}")
                    add_notification("Achats & Approvisionnements", ticket_num, f"Nouvelle demande d'achat soumise par {nom_departement} : {titre}", target_tab="3. Besoins & Achats")
                    
                    st.success(f"✅ Demande soumise avec succès ! Numéro de ticket attribué : **{ticket_num}**")
                    st.rerun()
                    
    with t2:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, titre, cahier_charges, montant, fournisseur, statut, etape_actuelle, avis_achats, avis_finance, motif_refus, date, fichier_devis, retour_remarque, fournisseur_retenu, numero_ticket FROM demandes ORDER BY id DESC")
        demandes = cursor.fetchall()
        conn.close()
        
        if demandes:
            # Filtres
            st.markdown('<div class="filter-bar"><div class="filter-bar-title">🔎 Filtrer les demandes</div>', unsafe_allow_html=True)
            c_f1, c_f2, c_f3 = st.columns(3)
            with c_f1:
                f_statut = st.selectbox("Statut", ["Tous", "En attente", "Validé", "Refusé", "Modification requise"], key="filtre_statut_achats")
            with c_f2:
                f_dept = st.selectbox("Département", ["Tous"] + sorted(list(set(d[1] for d in demandes))), key="filtre_dept_achats")
            with c_f3:
                f_rech = st.text_input("Recherche texte / ticket", value=selected_ticket or "", key="filtre_rech_achats")
            st.markdown('</div>', unsafe_allow_html=True)
            
            demandes_filtrees = []
            for d in demandes:
                d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_statut, d_etape, d_achats, d_fin, d_motif, d_date, d_fich, d_rem, d_retenu, d_ticket = d
                
                # Appliquer filtres
                if f_statut != "Tous" and f_statut.lower() not in d_statut.lower():
                    continue
                if f_dept != "Tous" and d_dept != f_dept:
                    continue
                if f_rech and f_rech.lower() not in f"{d_ticket} {d_titre} {d_dept} {d_cc}".lower():
                    continue
                demandes_filtrees.append(d)
            
            # Export dataframe
            df_exp = pd.DataFrame([{
                "Ticket": d[15], "Date": d[11], "Département": d[1], "Titre": d[2],
                "Montant estimé": d[4], "Fournisseur pressenti": d[5], "Fournisseur retenu": d[14],
                "Statut": d[6], "Étape": d[7], "Avis Achats": d[8], "Avis Finance": d[9]
            } for d in demandes_filtrees])
            afficher_boutons_export(df_exp, "suivi_demandes_achats", "Suivi des Demandes d'Achat", key_prefix="achats_suivi")
            
            for d in demandes_filtrees:
                d_id, d_dept, d_titre, d_cc, d_montant, d_fourn, d_statut, d_etape, d_achats, d_fin, d_motif, d_date, d_fich, d_rem, d_retenu, d_ticket = d
                
                titre_expander = f"{d_ticket or f'#ID-{d_id}'} | [{d_dept}] {d_titre} ({d_montant:,.2f} €) — Statut : {d_statut}"
                with st.expander(titre_expander):
                    c_info1, c_info2 = st.columns(2)
                    with c_info1:
                        st.markdown(f"**Ticket :** {d_ticket}")
                        st.markdown(f"**Émetteur :** {d_dept}")
                        st.markdown(f"**Date de soumission :** {d_date}")
                        st.markdown(f"**Montant estimé :** {d_montant:,.2f} €")
                        st.markdown(f"**Fournisseur pressenti :** {d_fourn or 'Aucun'}")
                        if d_retenu:
                            st.markdown(f"**Fournisseur retenu (Achats) :** **{d_retenu}** ✅")
                    with c_info2:
                        st.markdown(f"**Statut actuel :** {pill_statut(d_statut)}", unsafe_allow_html=True)
                        st.markdown(f"**Étape du workflow :** {d_etape}")
                        st.markdown(f"**Avis Achats :** {d_achats}")
                        st.markdown(f"**Avis Finance :** {d_fin}")
                    
                    st.markdown(f"**Spécifications / Cahier des charges :**\n{d_cc}")
                    
                    if d_fich:
                        chemin_f = os.path.join(DOSSIER_UPLOADS, d_fich)
                        if os.path.exists(chemin_f):
                            with open(chemin_f, "rb") as f_b:
                                st.download_button("📥 Télécharger le Devis / Fichier Joint", data=f_b.read(), file_name=d_fich, key=f"dl_devis_{d_id}")
                    
                    if d_rem:
                        st.warning(q := f"Remarques / Historique des modifications : {d_rem}")
                    if d_motif and "refusé" in d_statut.lower():
                        st.error(f"Motif du refus : {d_motif}")
                        
                    st.markdown("---")
                    
                    # --- ACTIONS SELON LE RÔLE ---
                    # 1. Émetteur peut modifier / annuler / supprimer sa demande si elle est en attente ou rejetée/demandée en modif
                    is_owner = (nom_departement == d_dept)
                    if is_owner and ("en attente" in d_statut.lower() or "modification" in d_statut.lower() or "refusé" in d_statut.lower()):
                        st.markdown("#### ✏️ Actions Émetteur")
                        col_m1, col_m2 = st.columns(2)
                        with col_m1:
                            if st.button("🔄 Modifier / Mettre à jour la demande", key=f"btn_modif_em_{d_id}"):
                                st.session_state[f"edition_active_{d_id}"] = True
                        with col_m2:
                            if st.button("❌ Annuler / Supprimer la demande", key=f"btn_annul_em_{d_id}"):
                                archiver_dans_corbeille(d_dept, "Demande d'Achat", f"{d_ticket} - {d_titre}", {"montant": d_montant, "statut": d_statut})
                                conn = get_db_connection()
                                cur = conn.cursor()
                                cur.execute("DELETE FROM demandes WHERE id = ?", (d_id,))
                                conn.commit()
                                conn.close()
                                ajouter_log("Annulation Demande", d_dept, f"Demande {d_ticket} annulée et supprimée par l'émetteur")
                                st.success("Demande annulée et supprimée.")
                                st.rerun()
                                
                        if st.session_state.get(f"edition_active_{d_id}", False):
                            with st.form(f"form_edit_demande_{d_id}"):
                                nv_titre = st.text_input("Titre", value=d_titre)
                                nv_cc = st.text_area("Cahier des charges", value=d_cc)
                                nv_montant = st.number_input("Montant (€)", value=d_montant)
                                nv_fourn = st.text_input("Fournisseur pressenti", value=d_fourn)
                                if st.form_submit_button("Enregistrer les modifications"):
                                    conn = get_db_connection()
                                    cur = conn.cursor()
                                    cur.execute("""
                                        UPDATE demandes SET titre=?, cahier_charges=?, montant=?, fournisseur=?, statut='En attente (Achats)', etape_actuelle='Achats', motif_refus=''
                                        WHERE id=?
                                    """, (nv_titre, nv_cc, nv_montant, nv_fourn, d_id))
                                    conn.commit()
                                    conn.close()
                                    st.session_state[f"edition_active_{d_id}"] = False
                                    ajouter_log("Modification Demande", d_dept, f"Demande {d_ticket} modifiée par l'émetteur")
                                    add_notification("Achats & Approvisionnements", d_ticket, f"La demande {d_ticket} a été modifiée par {d_dept} et est soumise à nouveau.", target_tab="3. Besoins & Achats")
                                    st.success("Demande mise à jour et renvoyée aux Achats !")
                                    st.rerun()

                    # 2. Rôle Achats (DEP12 ou fondateur)
                    if profil["type"] in ["achats", "fondateur"] and d_etape == "Achats":
                        st.markdown("#### ⚙️ Validation Achats & Fixation Fournisseur / Prix")
                        with st.form(f"form_val_achats_{d_id}"):
                            avis_ach = st.selectbox("Avis Achats", ["Favorable", "Défavorable (Refus)", "Demande de modification"], key=f"av_ach_{d_id}")
                            fourn_retenu = st.text_input("Fournisseur retenu (Définitif)", value=d_retenu or d_fourn)
                            montant_final = st.number_input("Montant définitif négocié (€)", min_value=0.0, value=d_montant)
                            remarques_ach = st.text_area("Commentaires / Conditions d'achat")
                            
                            if st.form_submit_button("Transmettre à la Finance"):
                                nouveau_statut = "En attente (Finance)" if avis_ach == "Favorable" else ("Refusé par les Achats" if avis_ach == "Défavorable (Refus)" else "Modification requise par les Achats")
                                nouvelle_etape = "Finance" if avis_ach == "Favorable" else "Clôturé"
                                
                                conn = get_db_connection()
                                cur = conn.cursor()
                                cur.execute("""
                                    UPDATE demandes SET statut=?, etape_actuelle=?, avis_achats=?, fournisseur_retenu=?, montant=?, retour_remarque=?, motif_refus=?
                                    WHERE id=?
                                """, (
                                    nouveau_statut, nouvelle_etape, avis_ach, fourn_retenu, montant_final, remarques_ach,
                                    remarques_ach if avis_ach != "Favorable" else "", d_id
                                ))
                                conn.commit()
                                conn.close()
                                
                                ajouter_log("Validation Achats", profil["nom"], f"Demande {d_ticket} traitée par les Achats: {avis_ach}")
                                if avis_ach == "Favorable":
                                    add_notification("Finance & Comptabilité", d_ticket, f"Demande {d_ticket} validée par les Achats, en attente d'avis financier.", target_tab="3. Besoins & Achats")
                                else:
                                    add_notification(d_dept, d_ticket, f"Votre demande {d_ticket} a reçu un retour des Achats: {avis_ach}", target_tab="3. Besoins & Achats")
                                
                                st.success("Validation Achats enregistrée et transmise !")
                                st.rerun()

                    # 3. Rôle Finance (DEP13 ou fondateur)
                    if profil["type"] in ["finance", "fondateur"] and d_etape == "Finance":
                        st.markdown("#### 💰 Validation Financière & Budgétaire")
                        with st.form(f"form_val_finance_{d_id}"):
                            avis_fin = st.selectbox("Avis Finance", ["Favorable (Financé)", "Défavorable (Refus budgétaire)", "Demande de modification"], key=f"av_fin_{d_id}")
                            remarques_fin = st.text_area("Commentaires financiers")
                            
                            if st.form_submit_button("Transmettre à la Direction Générale"):
                                nouveau_statut = "En attente (Direction)" if avis_fin.startswith("Favorable") else ("Refusé par la Finance" if "Défavorable" in avis_fin else "Modification requise par la Finance")
                                nouvelle_etape = "Direction" if avis_fin.startswith("Favorable") else "Clôturé"
                                
                                conn = get_db_connection()
                                cur = conn.cursor()
                                cur.execute("""
                                    UPDATE demandes SET statut=?, etape_actuelle=?, avis_finance=?, retour_remarque=?, motif_refus=?
                                    WHERE id=?
                                """, (
                                    nouveau_statut, nouvelle_etape, avis_fin, remarques_fin,
                                    remarques_fin if not avis_fin.startswith("Favorable") else "", d_id
                                ))
                                conn.commit()
                                conn.close()
                                
                                ajouter_log("Validation Finance", profil["nom"], f"Demande {d_ticket} traitée par la Finance: {avis_fin}")
                                if avis_fin.startswith("Favorable"):
                                    add_notification("Direction Générale", d_ticket, f"Demande {d_ticket} validée par la Finance, en attente d'approbation de la Direction.", target_tab="3. Besoins & Achats")
                                else:
                                    add_notification(d_dept, d_ticket, f"Votre demande {d_ticket} a reçu un retour financier: {avis_fin}", target_tab="3. Besoins & Achats")
                                
                                st.success("Avis financier enregistré et transmis à la Direction !")
                                st.rerun()

                    # 4. Rôle Fondateur / Direction Générale
                    if profil["type"] == "fondateur" and d_etape == "Direction":
                        st.markdown("#### 🏢 Approbation Définitive - Direction Générale")
                        with st.form(f"form_val_direction_{d_id}"):
                            decision_dir = st.selectbox("Décision Direction", ["Approuvé & Financé définitivement", "Refusé par la Direction", "Demande de modification"], key=f"dec_dir_{d_id}")
                            motif_dir = st.text_area("Commentaires / Instructions de la Direction")
                            
                            if st.form_submit_button("Valider la décision finale"):
                                nouveau_statut = "Validé / Approuvé" if "Approuvé" in decision_dir else ("Refusé" if "Refusé" in decision_dir else "Modification requise par la Direction")
                                
                                # Si validé définitivement, déduire du budget global
                                if "Approuvé" in decision_dir:
                                    b_total = get_valeur_globale("budget_global")
                                    b_solde = get_valeur_globale("solde_restant")
                                    nouveau_solde = max(0.0, b_solde - d_montant)
                                    set_valeur_globale("solde_restant", nouveau_solde)
                                
                                conn = get_db_connection()
                                cur = conn.cursor()
                                cur.execute("""
                                    UPDATE demandes SET statut=?, etape_actuelle='Clôturé', retour_remarque=?, motif_refus=?
                                    WHERE id=?
                                """, (
                                    nouveau_statut, motif_dir, motif_dir if "Approuvé" not in decision_dir else "", d_id
                                ))
                                conn.commit()
                                conn.close()
                                
                                ajouter_log("Approbation Direction", profil["nom"], f"Demande {d_ticket} : {decision_dir}")
                                add_notification(d_dept, d_ticket, f"Votre demande {d_ticket} a été traitée par la Direction : {decision_dir}", target_tab="3. Besoins & Achats")
                                
                                st.success("Décision de la Direction enregistrée avec succès !")
                                st.rerun()
        else:
            st.info("Aucune demande d'achat enregistrée.")

# ---------- Module Messagerie & Chat ----------
def afficher_module_messagerie(nom_departement, type_profil):
    st.subheader(f"💬 Messagerie Inter-Départements & Groupes — {nom_departement}")
    
    t1, t2 = st.tabs(["1. Discussions Actives", "2. Créer un Nouveau Groupe / Salon"])
    with t1:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nom_groupe, membres_json, createur, date_creation, archives_par FROM discussions ORDER BY id DESC")
        discussions = cursor.fetchall()
        conn.close()
        
        disc_accessibles = []
        for disc in discussions:
            d_id, d_nom, d_membres_j, d_createur, d_date, d_arch_j = disc
            membres = json.loads(d_membres_j) if d_membres_j else []
            archives = json.loads(d_arch_j) if d_arch_j else []
            if nom_departement in membres or type_profil == "fondateur":
                if nom_departement not in archives:
                    disc_accessibles.append(disc)
        
        if disc_accessibles:
            noms_disc = {f"[{d[1]}] Créé par {d[3]} ({d[4]})": d[0] for d in disc_accessibles}
            choix_label = st.selectbox("Sélectionner un salon de discussion", list(noms_disc.keys()), key="select_salon_chat")
            active_id = noms_disc[choix_label]
            st.session_state.discussion_active_id = active_id
            
            st.markdown("---")
            # Afficher les messages
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, expediteur, texte, date FROM messages_chat WHERE discussion_id = ? ORDER BY id ASC", (active_id,))
            messages = cursor.fetchall()
            conn.close()
            
            chat_container = st.container()
            with chat_container:
                if messages:
                    for m in messages:
                        m_id, m_exp, m_txt, m_date = m
                        is_me = (m_exp == nom_departement)
                        align = "right" if is_me else "left"
                        bg_color = "#e6f4ea" if is_me else "#f1f3f4"
                        st.markdown(f"""
                            <div style="text-align: {align}; margin-bottom: 10px;">
                                <div style="display: inline-block; background-color: {bg_color}; padding: 8px 12px; border-radius: 10px; max-width: 70%; text-align: left; border: 1px solid #dcdcdc;">
                                    <small style="color: #555; font-weight: bold;">{m_exp} - {m_date}</small><br>
                                    <span>{m_txt}</span>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("Aucun message dans ce salon pour l'instant. Démarrez la conversation !")
            
            with st.form(f"form_msg_{active_id}", clear_on_submit=True):
                nouveau_msg = st.text_input("Votre message...")
                c_s1, c_s2 = st.columns([1, 5])
                with c_s1:
                    submit_msg = st.form_submit_button("Envoyer")
                with c_s2:
                    archiver_salon = st.form_submit_button("Archiver ce salon pour moi")
                
                if submit_msg and nouveau_msg:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO messages_chat (discussion_id, expediteur, texte, date, lus_json)
                        VALUES (?, ?, ?, ?, ?)
                    """, (active_id, nom_departement, nouveau_msg, datetime.now().strftime("%d/%m %H:%M"), json.dumps([])))
                    conn.commit()
                    conn.close()
                    
                    # Notifier les autres membres du groupe
                    cursor = conn = get_db_connection()
                    cursor.execute("SELECT membres_json FROM discussions WHERE id = ?", (active_id,))
                    row_m = cursor.fetchone()
                    conn.close()
                    if row_m:
                        mems = json.loads(row_m[0]) if row_m[0] else []
                        for mem in mems:
                            if mem != nom_departement:
                                add_notification(mem, None, f"Nouveau message de {nom_departement} dans le salon", target_tab="4. Messagerie & Chat", target_disc=active_id)
                    
                    st.rerun()
                
                if archiver_salon:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT archives_par FROM discussions WHERE id = ?", (active_id,))
                    r_arch = cursor.fetchone()
                    archives = json.loads(r_arch[0]) if r_arch and r_arch[0] else []
                    if nom_departement not in archives:
                        archives.append(nom_departement)
                        cursor.execute("UPDATE discussions SET archives_par = ? WHERE id = ?", (json.dumps(archives), active_id))
                        conn.commit()
                    conn.close()
                    st.success("Salon archivé pour votre département.")
                    st.rerun()
        else:
            st.info("Aucune discussion active ou disponible.")
            
    with t2:
        tous_depts = [u["dept"] for u in UTILISATEURS.values()]
        with st.form("form_nouveau_groupe", clear_on_submit=True):
            nom_groupe = st.text_input("Nom du salon / sujet de discussion")
            membres_choisis = st.multiselect("Sélectionner les départements participants", tous_depts, default=[nom_departement])
            premier_message = st.text_area("Message initial (optionnel)")
            
            if st.form_submit_button("Créer le salon de discussion") and nom_groupe:
                if nom_departement not in membres_choisis:
                    membres_choisis.append(nom_departement)
                
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO discussions (nom_groupe, membres_json, createur, date_creation, archives_par)
                    VALUES (?, ?, ?, ?, ?)
                """, (nom_groupe, json.dumps(membres_choisis), nom_departement, datetime.now().strftime("%Y-%m-%d %H:%M"), json.dumps([])))
                disc_id = cursor.lastrowid
                
                if premier_message:
                    cursor.execute("""
                        INSERT INTO messages_chat (discussion_id, expediteur, texte, date, lus_json)
                        VALUES (?, ?, ?, ?, ?)
                    """, (disc_id, nom_departement, premier_message, datetime.now().strftime("%d/%m %H:%M"), json.dumps([])))
                
                conn.commit()
                conn.close()
                
                ajouter_log("Création Salon", nom_departement, f"Salon créé : {nom_groupe}")
                for mem in membres_choisis:
                    if mem != nom_departement:
                        add_notification(mem, None, f"Vous avez été ajouté au salon : {nom_groupe}", target_tab="4. Messagerie & Chat", target_disc=disc_id)
                
                st.success("Salon de discussion créé avec succès !")
                st.rerun()

# ---------- Module Journal de Bord ----------
def afficher_module_journal(nom_departement, type_profil):
    st.subheader(f"📖 Journal de Bord & Notes de Service — {nom_departement}")
    t1, t2 = st.tabs(["1. Rédiger une Note", "2. Consulter le Journal Global"])
    with t1:
        with st.form(f"form_journal_{nom_departement}", clear_on_submit=True):
            note = st.text_area("Note de service, événement marquant ou compte-rendu")
            if st.form_submit_button("Enregistrer dans le journal") and note:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO journal_bord (departement, auteur, note, date_note, heure_note)
                    VALUES (?, ?, ?, ?, ?)
                """, (nom_departement, profil["nom"], note, datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M")))
                conn.commit()
                conn.close()
                ajouter_log("Journal de Bord", nom_departement, "Nouvelle note enregistrée")
                st.success("Note enregistrée dans le journal de bord !")
                st.rerun()
    with t2:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, departement, auteur, note, date_note, heure_note FROM journal_bord ORDER BY id DESC")
        notes = cursor.fetchall()
        conn.close()
        
        if notes:
            df_j = pd.DataFrame([{
                "ID": n[0], "Département": n[1], "Auteur": n[2], "Date": f"{n[4]} à {n[5]}", "Note": n[3]
            } for n in notes])
            afficher_boutons_export(df_j, "journal_de_bord", "Journal de Bord", key_prefix="journal_bord")
            
            for n in notes:
                n_id, n_dept, n_auteur, n_note, n_date, n_heure = n
                with st.expander(f"📝 [{n_dept}] Note de {n_auteur} ({n_date} à {n_heure})"):
                    st.write(n_note)
                    if n_dept == nom_departement or type_profil == "fondateur":
                        if st.button("🗑️ Supprimer cette note", key=f"del_note_{n_id}"):
                            archiver_dans_corbeille(n_dept, "Note Journal", n_note[:50], {"auteur": n_auteur, "date": n_date})
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM journal_bord WHERE id = ?", (n_id,))
                            conn.commit()
                            conn.close()
                            ajouter_log("Suppression Note", n_dept, "Note de journal supprimée")
                            st.success("Note supprimée et archivée.")
                            st.rerun()
        else:
            st.info("Aucune note dans le journal de bord.")

# ---------- Module Recherche Globale ----------
def afficher_module_recherche(nom_departement, type_profil):
    st.subheader("🔍 Moteur de Recherche Global & Unifié")
    terme = st.text_input("Rechercher dans tout le système (Études, CDC, Demandes, Journal)...")
    if terme:
        t_low = terme.lower()
        st.markdown(f"### Résultats pour : *{terme}*")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Études
        cursor.execute("SELECT departement, titre, date FROM etudes_metier WHERE LOWER(titre) LIKE ? OR LOWER(donnees_json) LIKE ?", (f"%{t_low}%", f"%{t_low}%"))
        res_etudes = cursor.fetchall()
        
        # CDC
        cursor.execute("SELECT departement, titre, date FROM cahiers_charges WHERE LOWER(titre) LIKE ? OR LOWER(contenu) LIKE ?", (f"%{t_low}%", f"%{t_low}%"))
        res_cdcs = cursor.fetchall()
        
        # Demandes
        cursor.execute("SELECT numero_ticket, departement, titre, statut FROM demandes WHERE LOWER(numero_ticket) LIKE ? OR LOWER(titre) LIKE ? OR LOWER(cahier_charges) LIKE ?", (f"%{t_low}%", f"%{t_low}%", f"%{t_low}%"))
        res_dem = cursor.fetchall()
        
        conn.close()
        
        if res_etudes:
            st.markdown("#### ⚙️ Études techniques correspondantes")
            for e in res_etudes:
                st.write(f"- **[{e[0]}]** {e[1]} ({e[2]})")
        if res_cdcs:
            st.markdown("#### 📋 Cahiers des charges correspondants")
            for c in res_cdcs:
                st.write(f"- **[{c[0]}]** {c[1]} ({c[2]})")
        if res_dem:
            st.markdown("#### 🛒 Demandes d'achat correspondantes")
            for d in res_dem:
                st.write(f"- **{d[0]}** [{d[1]}] {d[2]} — *Statut : {d[3]}*")
                
        if not res_etudes and not res_cdcs and not res_dem:
            st.info("Aucun résultat trouvé pour cette recherche.")

# ---------- Pôle de Contrôle (Suivi Global) ----------
def afficher_module_controle(nom_departement, type_profil):
    st.subheader("📊 Pôle de Contrôle & Suivi Global de l'Activité")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT numero_ticket, departement, titre, montant, statut, etape_actuelle, date FROM demandes ORDER BY id DESC")
    toutes_demandes = cursor.fetchall()
    conn.close()
    
    if toutes_demandes:
        df_ctrl = pd.DataFrame([{
            "Ticket": d[0], "Département": d[1], "Intitulé": d[2],
            "Montant (€)": d[3], "Statut": d[4], "Étape": d[5], "Date": d[6]
        } for d in toutes_demandes])
        
        afficher_boutons_export(df_ctrl, "controle_global_achats", "Suivi Global des Achats", key_prefix="ctrl_global")
        
        st.markdown("---")
        st.markdown("#### Tableau synthétique de pilotage")
        st.dataframe(df_ctrl, use_container_width=True)
    else:
        st.info("Aucune donnée de suivi global disponible.")

# ---------- Module Statistiques ----------
def afficher_module_stats(nom_departement, type_profil):
    st.subheader("📈 Statistiques & Indicateurs Clés de Performance (KPI)")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT departement, montant, statut FROM demandes")
    data_dem = cursor.fetchall()
    conn.close()
    
    if data_dem:
        df_stats = pd.DataFrame(data_dem, columns=["Département", "Montant", "Statut"])
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Nombre total de demandes", len(df_stats))
        c2.metric("Montant total demandé", f"{df_stats['Montant'].sum():,.2f} €")
        c3.metric("Montant moyen par demande", f"{df_stats['Montant'].mean():,.2f} €" if len(df_stats) > 0 else "0.00 €")
        
        st.markdown("---")
        st.markdown("#### Répartition des montants par département")
        pivot_dept = df_stats.groupby("Département")["Montant"].sum().reset_index()
        st.bar_chart(pivot_dept.set_index("Département"))
        
        st.markdown("---")
        afficher_boutons_export(pivot_dept, "statistiques_kpi", "Rapport Statistiques et KPI", key_prefix="stats_kpi")
    else:
        st.info("Données insuffisantes pour générer les statistiques.")

# ---------- Module Audit & Traçabilité ----------
def afficher_module_audit(nom_departement, type_profil):
    st.subheader("🕵️ Audit, Traçabilité & Suivi des Connexions")
    
    t1, t2 = st.tabs(["1. Journal des Actions (Logs)", "2. Système de Pointage & Connexions Utilisateurs"])
    with t1:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, date, acteur, action, details FROM logs_audit ORDER BY id DESC LIMIT 200")
        logs = cursor.fetchall()
        conn.close()
        
        if logs:
            df_logs = pd.DataFrame(logs, columns=["ID", "Date", "Acteur", "Action", "Détails"])
            afficher_boutons_export(df_logs, "journal_audit_actions", "Journal d'Audit et Traçabilité", key_prefix="audit_logs")
            st.dataframe(df_logs, use_container_width=True)
        else:
            st.info("Aucun log d'audit enregistré.")
            
    with t2:
        st.markdown("#### Suivi de l'activité et des connexions des collaborateurs")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT date, acteur, action, details FROM logs_audit WHERE action = 'Connexion' ORDER BY id DESC")
        conn_logs = cursor.fetchall()
        conn.close()
        
        if conn_logs:
            df_conn = pd.DataFrame(conn_logs, columns=["Date / Heure", "Collaborateur", "Action", "Détails"])
            # Calcul du nombre de connexions par utilisateur
            stats_conn = df_conn.groupby("Collaborateur").size().reset_index(name="Nombre de connexions")
            afficher_boutons_export(stats_conn, "pointage_connexions", "Rapport de Pointage et Activité", key_prefix="pointage_conn")
            st.dataframe(stats_conn, use_container_width=True)
            st.markdown("##### Historique détaillé des connexions")
            st.dataframe(df_conn, use_container_width=True)
        else:
            st.info("Aucune donnée de connexion enregistrée.")

# ---------- Module Corbeille ----------
def afficher_module_corbeille(nom_departement, type_profil):
    st.subheader("🗑️ Corbeille & Éléments Archivés / Supprimés")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, departement_auteur, type_element, resume, details_json, date_suppression FROM corbeille_archives ORDER BY id DESC")
    archives = cursor.fetchall()
    conn.close()
    
    if archives:
        df_corb = pd.DataFrame([{
            "ID": a[0], "Département": a[1], "Type": a[2], "Résumé": a[3], "Date suppression": a[5]
        } for a in archives])
        afficher_boutons_export(df_corb, "corbeille_archives", "Archives et Suppressions", key_prefix="corbeille_exp")
        
        for a in archives:
            a_id, a_dept, a_type, a_res, a_json, a_date = a
            with st.expander(f"🗑️ [{a_type}] {a_res} (Supprimé par {a_dept} le {a_date})"):
                st.json(json.loads(a_json) if a_json else {})
                if type_profil == "fondateur":
                    if st.button("🗑️ Supprimer définitivement", key=f"perma_del_{a_id}"):
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM corbeille_archives WHERE id = ?", (a_id,))
                        conn.commit()
                        conn.close()
                        st.success("Élément supprimé définitivement.")
                        st.rerun()
    else:
        st.info("La corbeille est vide.")

# ==========================================
# ROUTAGE DE L'ONGLET ACTIF
# ==========================================
tab_courant = st.session_state.tab_actif

if tab_courant == "1. Études & Ingénierie":
    afficher_module_etudes(nom_dept, profil["type"])
elif tab_courant == "2. Cahiers des Charges":
    afficher_module_cahiers_charges(nom_dept, profil["type"])
elif tab_courant == "3. Besoins & Achats":
    afficher_module_achats(nom_dept, profil["type"])
elif tab_courant == "4. Messagerie & Chat":
    afficher_module_messagerie(nom_dept, profil["type"])
elif tab_courant == "📖 Journal de Bord":
    afficher_module_journal(nom_dept, profil["type"])
elif tab_courant == "🔍 Recherche Globale":
    afficher_module_recherche(nom_dept, profil["type"])
elif tab_courant == "📊 Pôle de Contrôle (Suivi Global)":
    afficher_module_controle(nom_dept, profil["type"])
elif tab_courant == "📈 Statistiques":
    afficher_module_stats(nom_dept, profil["type"])
elif tab_courant == "🕵️ Audit & Traçabilité":
    afficher_module_audit(nom_dept, profil["type"])
elif tab_courant == "🗑️ Corbeille & Historique Suppressions":
    afficher_module_corbeille(nom_dept, profil["type"])
