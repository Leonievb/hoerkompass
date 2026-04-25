"""
app.py – Hörkompass: Karte mit Ampelsystem, Kommentaren und Community-Features
Starten: streamlit run app.py
"""

import pandas as pd
import folium
import streamlit as st
from streamlit_folium import st_folium
from datetime import datetime
import os
import json
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Hörkompass", page_icon="🦻", layout="wide")
st.title("🦻 Hörkompass")
st.caption("Veranstaltungsorte mit Hörunterstützung – finde barrierearme Orte in deiner Nähe")
st.markdown(
    "### _Mithören. Dabeisein. Erleben._  \n\n" \
    "**Nicht alles, was “barrierefrei” ist, ist auch hörfreundlich.**  \n\n" \
    "Deshalb gibt es den Hörkompass: Entdecke Veranstaltungsorte mit Hörunterstützung - geprüft, bewertet und empfohlen  von der Community für die Community.  \n\n" \
    "Klicke auf einen Ort für Details. Bewertungen und Kommentare findest du direkt unterhalb der Karte." \
)

# --- Google Sheets Verbindung ---
SHEET_ID = "1x3QbABHy1qYdWLIIsya62j_z_G5EOrQ_MYwvUIpBC9k"
SCOPES   = ["https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def get_gsheet_client():
    """Verbindung zu Google Sheets – lokal via JSON-Datei, online via Streamlit Secrets."""
    if os.path.exists("google_credentials.json"):
        # Lokal: JSON-Datei direkt verwenden
        creds = Credentials.from_service_account_file("google_credentials.json", scopes=SCOPES)
    else:
        # Streamlit Cloud: Credentials aus st.secrets
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=SCOPES
        )
    return gspread.authorize(creds)

def get_worksheet(tab_name: str):
    client = get_gsheet_client()
    sheet  = client.open_by_key(SHEET_ID)
    return sheet.worksheet(tab_name)

def sheet_to_df(tab_name: str) -> pd.DataFrame:
    """Liest einen Tab als DataFrame."""
    try:
        ws   = get_worksheet(tab_name)
        data = ws.get_all_records()
        return pd.DataFrame(data).astype(str)
    except Exception:
        return pd.DataFrame()

def clear_kommentare_cache():
    """Cache nach dem Schreiben leeren damit neue Daten sofort sichtbar sind."""
    load_kommentare.clear()

def append_row(tab_name: str, row: dict):
    """Hängt eine neue Zeile an den Tab an."""
    ws     = get_worksheet(tab_name)
    header = ws.row_values(1)
    neue_zeile = [str(row.get(col, "")) for col in header]
    ws.append_row(neue_zeile, value_input_option="RAW")

# --- Daten laden ---
@st.cache_data
def load_orte():
    df = pd.read_csv("orte_geocoded.csv", dtype=str, sep=";", encoding="utf-8-sig")
    df.columns = df.columns.str.strip()
    df = df[df["lat"].notna() & (df["lat"].str.strip() != "")]
    df["lat"] = df["lat"].astype(float)
    df["lon"] = df["lon"].astype(float)
    return df

@st.cache_data(ttl=60)
def load_kommentare() -> pd.DataFrame:
    """Lädt Kommentare aus Google Sheets – gecacht für 60 Sekunden."""
    df = sheet_to_df("kommentare")
    for col in ["ampel","verwendete_anlage","geraet"]:
        if col not in df.columns:
            df[col] = ""
    return df

def save_kommentar(ort_id, autor, kommentar, ampel, verwendete_anlage, geraet):
    df_k = load_kommentare()
    if df_k.empty or df_k["kommentar_id"].isna().all() or (df_k["kommentar_id"] == "").all():
        neue_id = "K0001"
    else:
        letzte_num = df_k["kommentar_id"].dropna().str.extract(r"(\d+)")[0]
        letzte_num = pd.to_numeric(letzte_num, errors="coerce").dropna()
        neue_id = f"K{int(letzte_num.max()) + 1:04d}" if not letzte_num.empty else "K0001"
    append_row("kommentare", {
        "kommentar_id":      neue_id,
        "ort_id":            ort_id,
        "datum":             datetime.now().strftime("%Y-%m-%d"),
        "autor_name":        autor if autor.strip() else "Anonym",
        "kommentar":         kommentar,
        "ampel":             ampel,
        "verwendete_anlage": ", ".join(verwendete_anlage),
        "geraet":            geraet,
        "hilfreich_votes":   "0",
        "moderiert":         "nein",
    })

def save_neuer_ort(name, adresse, kategorie, kategorie_sonstige, anlagetypen, anlagetyp_sonstige, hinweise, website, email):
    df_n = sheet_to_df("neueorte")
    if df_n.empty or (df_n.get("eintrag_id", pd.Series()) == "").all():
        neue_id = "N0001"
    else:
        letzte_num = df_n["eintrag_id"].dropna().str.extract(r"(\d+)")[0]
        letzte_num = pd.to_numeric(letzte_num, errors="coerce").dropna()
        neue_id = f"N{int(letzte_num.max()) + 1:04d}" if not letzte_num.empty else "N0001"
    append_row("neueorte", {
        "eintrag_id": neue_id, "datum": datetime.now().strftime("%Y-%m-%d"),
        "name": name, "adresse": adresse, "kategorie": kategorie,
        "kategorie_sonstige": kategorie_sonstige, "anlagetyp": ", ".join(anlagetypen),
        "anlagetyp_sonstige": anlagetyp_sonstige, "hinweise": hinweise,
        "website": website, "email_einsender": email, "status": "neu",
    })

def save_feedback(typ, betreff, nachricht, email):
    df_f = sheet_to_df("feedback")
    if df_f.empty or (df_f.get("feedback_id", pd.Series()) == "").all():
        neue_id = "F0001"
    else:
        letzte_num = df_f["feedback_id"].dropna().str.extract(r"(\d+)")[0]
        letzte_num = pd.to_numeric(letzte_num, errors="coerce").dropna()
        neue_id = f"F{int(letzte_num.max()) + 1:04d}" if not letzte_num.empty else "F0001"
    append_row("feedback", {
        "feedback_id": neue_id, "datum": datetime.now().strftime("%Y-%m-%d"),
        "typ": typ, "betreff": betreff, "nachricht": nachricht, "email_einsender": email,
    })

df = load_orte()

# --- Konstanten ---
KATEGORIE_FARBEN = {
    "theater":"#D53E29","konzerthaus":"#A13336","oper":"#A23236","musical":"#D53E29",
    "kino":"#F49630","kirche":"#38AADD","museum":"#72B027","gedenkstaette":"#728224",
    "bibliothek":"#BBFA70","bildung":"#CF51B6","behoerde":"#575757",
    "veranstaltungszentrum":"#446978","planetarium":"#0067A3","sonstiges":"#adb5bd",
}
KATEGORIE_FOLIUM_FARBEN = {
    "theater":"red","konzerthaus":"darkred","oper":"darkred","musical":"red",
    "kino":"orange","kirche":"blue","museum":"green","gedenkstaette":"darkgreen",
    "bibliothek":"lightgreen","bildung":"purple","behoerde":"gray",
    "veranstaltungszentrum":"cadetblue","planetarium":"darkblue","sonstiges":"lightgray",
}
KATEGORIE_LABELS = {
    "theater":"Theater","konzerthaus":"Konzerthaus","oper":"Oper","musical":"Musical",
    "kino":"Kino","kirche":"Kirche","museum":"Museum","gedenkstaette":"Gedenkstätte",
    "bibliothek":"Bibliothek","bildung":"Bildung","behoerde":"Behörde",
    "veranstaltungszentrum":"Veranstaltungszentrum","planetarium":"Planetarium",
    "sonstiges":"Sonstiges","anderes":"Anderes (bitte beschreiben)",
}
KATEGORIE_ICONS = {
    "theater":"fa-solid fa-masks-theater","konzerthaus":"fa-solid fa-music",
    "oper":"fa-solid fa-music","musical":"fa-solid fa-masks-theater",
    "kino":"fa-solid fa-film","kirche":"fa-solid fa-church",
    "museum":"fa-solid fa-building-columns","gedenkstaette":"fa-solid fa-monument",
    "bibliothek":"fa-solid fa-book","bildung":"fa-solid fa-graduation-cap",
    "behoerde":"fa-solid fa-landmark","veranstaltungszentrum":"fa-solid fa-calendar-days",
    "planetarium":"fa-solid fa-star","sonstiges":"fa-solid fa-circle",
}
ANLAGETYP_ICONS = {
    "induktion":"🔵 Induktion (T-Spule, Hörschleife)","infrarot":"🟡 Infrarot","funk":"🟠 Funk",
    "mobile_connect":"📱 MobileConnect",
    "untertitel":"💬 Untertitel",
    "audioguide":"🎧 Audioguide","rogeron_vorhanden":"🎙 Roger On (vorhanden)",
    "rogeron_mitbringen":"🎙 Roger On (mitbringen)",
    "sitzplatzreservierung":"💺 Sitzplatzreservierung",
    "auracast":"🛜 Auracast",
    "DGS (ausgewählt)":"🤟 DGS (ausgewählte Events)",
    "keine":"❌ Keine",
    "anderes":"➕ Anderes (bitte beschreiben)",
}
KONFESSION_LABELS = {
    "ev":"Evangelisch-lutherisch","rk":"Römisch-katholisch","fk":"Freikirchlich",
    "rf":"Evangelisch-reformiert","oek":"Ökumenisch",
}
ANLAGE_STATUS_LABELS = {
    "funktioniert":"✅ Funktioniert","defekt":"❌ Defekt","nicht_getestet":"❓ Nicht getestet",
}
AMPEL_OPTIONEN = {
    "gruen":  "🟢 Hat super funktioniert",
    "gelb":   "🟡 Hat bedingt / mit Problemen funktioniert",
    "rot":    "🔴 Hat gar nicht funktioniert",
    "anderes":"💬 Anderes (Frage / allgemeiner Kommentar)",
}
AMPEL_WERTE  = {"gruen": 3, "gelb": 2, "rot": 1, "anderes": None}
AMPEL_FARBEN = {"gruen": "#2ecc71", "gelb": "#f1c40f", "rot": "#e74c3c", "anderes": "#adb5bd"}
AMPEL_TEXTE  = {
    3: ("gruen", "#2ecc71", "Gut zugänglich"),
    2: ("gelb",  "#f1c40f", "Bedingt zugänglich"),
    1: ("rot",   "#e74c3c", "Schwer zugänglich"),
}
GERAET_OPTIONEN = [
    "Hörgerät", "CI (Cochlea-Implantat)",
    "Hörgerät + CI", "Baha / Knochenverankertes Hörgerät",
    "Keins", "Anderes",
]

# --- Hilfsfunktionen ---
def folium_farbe(k): return KATEGORIE_FOLIUM_FARBEN.get(str(k).strip().lower(), "lightgray")
def hex_farbe(k):    return KATEGORIE_FARBEN.get(str(k).strip().lower(), "#adb5bd")
def folium_icon(k):  return KATEGORIE_ICONS.get(str(k).strip().lower(), "fa-solid fa-circle")

def get_anlagetyp_list(s):
    if pd.isna(s) or not str(s).strip(): return []
    return [t.strip() for t in str(s).split(",") if t.strip()]

def format_anlagetyp_html(s):
    if pd.isna(s) or not str(s).strip(): return "–"
    return "<br>".join([ANLAGETYP_ICONS.get(t.strip(), t.strip()) for t in str(s).split(",") if t.strip()])

def val(v):
    return "" if pd.isna(v) or str(v).strip().lower() in ["nan","none",""] else str(v).strip()

def website_link_html(website, label="🌐 Website"):
    if not website: return ""
    if "@" in website and not website.startswith("http"):
        return f'<a href="mailto:{website}" target="_blank">📧 {website}</a><br>'
    url = website if website.startswith("http") else f"https://{website}"
    return f'<a href="{url}" target="_blank">{label}</a><br>'

def berechne_ampel(ort_id: str) -> dict:
    kommentare = load_kommentare()
    if kommentare.empty:
        return {"farbe": "#adb5bd", "text": "Noch nicht bewertet", "schnitt": None, "anzahl": 0}
    ort_k = kommentare[
        (kommentare["ort_id"] == ort_id) &
        (kommentare["moderiert"].str.strip().str.lower() == "ja") &
        (kommentare["ampel"].isin(["gruen","gelb","rot"]))
    ]
    if ort_k.empty:
        return {"farbe": "#adb5bd", "text": "Noch nicht bewertet", "schnitt": None, "anzahl": 0}
    werte = ort_k["ampel"].map(AMPEL_WERTE).dropna()
    if werte.empty:
        return {"farbe": "#adb5bd", "text": "Noch nicht bewertet", "schnitt": None, "anzahl": 0}
    schnitt  = werte.mean()
    gerundet = max(1, min(3, round(schnitt)))
    key, farbe, text = AMPEL_TEXTE[gerundet]
    return {"farbe": farbe, "text": text, "schnitt": round(schnitt, 1), "anzahl": len(werte)}

def ampel_html(ort_id: str, fontsize: str = "13px") -> str:
    a = berechne_ampel(ort_id)
    if a["schnitt"] is None:
        return f'<span style="color:#adb5bd; font-size:{fontsize};">⬤ Noch nicht bewertet</span>'
    return (
        f'<span style="color:{a["farbe"]}; font-size:{fontsize};">⬤</span> '
        f'<span style="font-size:{fontsize};">{a["text"]}</span> '
        f'<span style="color:#aaa; font-size:11px;">· {a["schnitt"]}/3 aus {a["anzahl"]} '
        f'Bewertung{"en" if a["anzahl"] != 1 else ""}</span>'
    )

def build_popup(row):
    name         = val(row.get("name")) or "–"
    adresse      = val(row.get("adresse"))
    plz          = val(row.get("plz"))
    stadtteil    = val(row.get("stadtteil"))
    kategorie    = KATEGORIE_LABELS.get(val(row.get("kategorie")), val(row.get("kategorie")))
    anlage       = format_anlagetyp_html(val(row.get("anlagetyp")))
    hinweise     = val(row.get("anlage_hinweise"))
    website      = val(row.get("website"))
    verifiziert  = val(row.get("verifiziert"))
    konfession   = val(row.get("konfession"))
    ermaessigung = val(row.get("Ermäßigung"))
    quelle       = val(row.get("quelle"))
    quelle_datum = val(row.get("quelle_datum"))
    ort_id       = val(row.get("ort_id"))

    adresse_zeile     = " ".join(filter(None,[adresse,plz,stadtteil])) or "–"
    website_html      = website_link_html(website)
    hinweise_html     = f"<b>Hinweise</b><br>{hinweise}<br><br>" if hinweise else ""
    konfession_html   = f'⛪ {KONFESSION_LABELS.get(konfession,konfession)}<br>' if konfession else ""
    ermaessigung_html = f'🎟 <b>Ermäßigung:</b><br>{ermaessigung}<br><br>' if ermaessigung else ""
    if verifiziert == "ja":
        verifiziert_html = '<span style="color:green">✅ Verifiziert</span><br>'
    elif verifiziert == "in_reparatur":
        verifiziert_html = '<span style="color:orange">🔧 In Reparatur</span><br>'
    else:
        verifiziert_html = '<span style="color:gray">❓ Noch nicht community-verifiziert</span><br>'
    quelle_parts = list(filter(None,[quelle,quelle_datum]))
    quelle_html  = f'<span style="color:#aaa;font-size:11px;">Quelle: {" · ".join(quelle_parts)}</span>' if quelle else ""

    return f"""
    <div style="min-width:240px;font-family:sans-serif;font-size:13px;">
        <b style="font-size:14px;">{name}</b><br>
        <span style="color:gray">{kategorie}</span><br>
        {konfession_html}<hr style="margin:4px 0">
        📍 {adresse_zeile}<br><br>
        <b>Community-Bewertung</b><br>{ampel_html(ort_id)}<br><br>
        <b>Mehr Zugänglichkeit durch:</b><br>{anlage}<br><br>
        {ermaessigung_html}{hinweise_html}{verifiziert_html}{website_html}
        <hr style="margin:6px 0">{quelle_html}
    </div>"""

def zeige_sidebar_info(row):
    name         = val(row.get("name")) or "–"
    adresse      = val(row.get("adresse"))
    plz          = val(row.get("plz"))
    stadtteil    = val(row.get("stadtteil"))
    bezirk       = val(row.get("bezirk"))
    kategorie    = KATEGORIE_LABELS.get(val(row.get("kategorie")), val(row.get("kategorie")))
    anlagetypen  = get_anlagetyp_list(val(row.get("anlagetyp")))
    hinweise     = val(row.get("anlage_hinweise"))
    website      = val(row.get("website"))
    verifiziert  = val(row.get("verifiziert"))
    konfession   = val(row.get("konfession"))
    ermaessigung = val(row.get("Ermäßigung"))
    quelle       = val(row.get("quelle"))
    quelle_datum = val(row.get("quelle_datum"))
    farbe        = hex_farbe(val(row.get("kategorie")))
    ort_id       = val(row.get("ort_id"))

    col_titel, col_close = st.sidebar.columns([4,1])
    with col_close:
        if st.button("✕", key="close_btn", help="Auswahl schließen"):
            st.session_state["angeklickter_ort"] = None; st.rerun()

    konfession_str    = f", {KONFESSION_LABELS.get(konfession,konfession)}" if konfession else ""
    adresse_zeile     = " ".join(filter(None,[adresse,plz,stadtteil,f"({bezirk})" if bezirk else ""])) or "–"
    anlage_zeilen     = "".join(f"{ANLAGETYP_ICONS.get(a,a)}<br>" for a in anlagetypen) if anlagetypen else ""
    anlage_header     = "<b>Mehr Zugänglichkeit durch:</b><br>" if anlagetypen else ""
    ermaessigung_html = f"🎟 <b>Ermäßigung:</b><br> {ermaessigung}<br><br>" if ermaessigung else ""
    hinweise_html     = f"<b>Hinweise</b><br><i>{hinweise}</i><br><br>" if hinweise else ""
    website_html      = website_link_html(website)
    quelle_str        = " · ".join(filter(None,[quelle,quelle_datum]))
    quelle_html       = f'<span style="color:#aaa;font-size:11px;">Quelle: {quelle_str}</span>' if quelle else ""
    if verifiziert == "ja":
        verifiziert_html = '<span style="color:green">✅ Verifiziert</span><br>'
    elif verifiziert == "in_reparatur":
        verifiziert_html = '<span style="color:orange">🔧 In Reparatur</span><br>'
    else:
        verifiziert_html = '<span style="color:gray">❓ Noch nicht community-verifiziert</span><br>'

    optional_html = "".join([
        f"<b>Community-Bewertung</b><br>{ampel_html(ort_id)}<br><br>",
        anlage_header, anlage_zeilen, "<br>" if anlage_zeilen else "",
        ermaessigung_html, hinweise_html, verifiziert_html, website_html,
        f"<br>{quelle_html}" if quelle_html else "",
    ])
    st.sidebar.markdown(
        f'<div style="font-size:13px;line-height:1.6;">'
        f'<span style="font-size:20px;font-weight:bold;">Ausgewählter Ort</span><br>'
        f'<span style="color:{farbe};font-size:16px;font-weight:bold;">{name}</span><br>'
        f'<span style="color:gray;font-size:12px;">{kategorie}{konfession_str}</span><br>'
        f'📍 {adresse_zeile}<br><br>{optional_html}</div>',
        unsafe_allow_html=True)
    st.sidebar.markdown("---")

# --- Dialoge ---
@st.dialog("➕ Neuen Ort vorschlagen", width="large")
def dialog_neuer_ort():
    st.caption("Vielen Dank für deinen Beitrag! Vorschläge werden nach Prüfung in die Karte aufgenommen.")
    name    = st.text_input("Name des Ortes *", placeholder="z.B. Kulturzentrum Altona")
    adresse = st.text_input("Adresse *", placeholder="z.B. Museumstraße 17, 22765 Hamburg")
    kat_optionen = list(KATEGORIE_LABELS.keys()); kat_labels = list(KATEGORIE_LABELS.values())
    kat_wahl = st.selectbox("Kategorie *", options=kat_labels)
    kat_key  = kat_optionen[kat_labels.index(kat_wahl)]; kat_sonstige = ""
    if kat_key == "anderes": kat_sonstige = st.text_input("Welche Kategorie? Bitte beschreiben:")
    anlage_optionen = list(ANLAGETYP_ICONS.keys()); anlage_labels = list(ANLAGETYP_ICONS.values())
    anlage_wahl = st.multiselect("Art der Hörunterstützung", options=anlage_labels)
    anlage_keys = [anlage_optionen[anlage_labels.index(l)] for l in anlage_wahl]; anlage_sonstige = ""
    if "anderes" in anlage_keys: anlage_sonstige = st.text_input("Welcher Art(en) der Hörunterstützung? Bitte beschreiben:")
    hinweise = st.text_area("Hinweise", placeholder="z.B. Induktionsschleife nur in den ersten 5 Reihen", max_chars=500)
    website  = st.text_input("Website oder E-Mail", placeholder="z.B. www.beispiel.de")
    email    = st.text_input("Deine E-Mail (optional)", placeholder="deine@email.de")
    st.markdown("---")
    col_ab, col_cancel = st.columns([1,1])
    with col_ab:
        if st.button("✅ Vorschlag einreichen", use_container_width=True):
            if not name.strip(): st.warning("Bitte gib einen Namen ein.")
            elif not adresse.strip(): st.warning("Bitte gib eine Adresse ein.")
            else:
                save_neuer_ort(name.strip(),adresse.strip(),kat_key,kat_sonstige.strip(),
                               anlage_keys,anlage_sonstige.strip(),hinweise.strip(),website.strip(),email.strip())
                st.success("Danke! Dein Vorschlag wurde gespeichert und wird geprüft.")
                st.balloons()
    with col_cancel:
        if st.button("Abbrechen", use_container_width=True): st.rerun()

@st.dialog("💡 Feedback & Ideen", width="large")
def dialog_feedback():
    st.caption("Dein Feedback hilft dabei, diesen Hörkompass besser zu machen!")
    FEEDBACK_TYPEN = {"verbesserung":"🔧 Verbesserungsvorschlag","fehler":"🐛 Fehlermeldung",
                      "addon":"✨ Add-on-Wunsch","anderes":"💬 Anderes"}
    typ_label = st.selectbox("Art des Feedbacks *", options=list(FEEDBACK_TYPEN.values()))
    typ_key   = [k for k,v in FEEDBACK_TYPEN.items() if v==typ_label][0]
    betreff   = st.text_input("Betreff *", placeholder="z.B. Filterfunktion verbessern", max_chars=100)
    nachricht = st.text_area("Beschreibung *", placeholder="Beschreibe dein Feedback so genau wie möglich...", max_chars=1000)
    email     = st.text_input("Deine E-Mail (optional)", placeholder="deine@email.de")
    st.markdown("---")
    col_ab, col_cancel = st.columns([1,1])
    with col_ab:
        if st.button("✅ Feedback einreichen", use_container_width=True):
            if not betreff.strip(): st.warning("Bitte gib einen Betreff ein.")
            elif not nachricht.strip(): st.warning("Bitte gib eine Beschreibung ein.")
            else:
                save_feedback(typ_key,betreff.strip(),nachricht.strip(),email.strip())
                st.success("Danke für dein Feedback! 🙏"); st.balloons()
    with col_cancel:
        if st.button("Abbrechen", use_container_width=True, key="cancel_feedback"): st.rerun()

# --- Session State ---
if "angeklickter_ort" not in st.session_state: st.session_state["angeklickter_ort"] = None
if "suche_counter"    not in st.session_state: st.session_state["suche_counter"] = 0

angeklickter_ort = st.session_state["angeklickter_ort"]

# --- Sidebar ---
if angeklickter_ort:
    treffer = df[df["name"] == angeklickter_ort]
    if not treffer.empty: zeige_sidebar_info(treffer.iloc[0])

st.sidebar.header("🔍 Filter")
col_suche, col_reset = st.sidebar.columns([4,1])
with col_suche:
    suche = st.text_input("Suche", placeholder="🔎 z.B. Elbphilharmonie",
                          label_visibility="collapsed", key=f"suche_{st.session_state['suche_counter']}")
with col_reset:
    if st.button("✕", key="reset_suche", help="Suche zurücksetzen"):
        st.session_state["suche_counter"] += 1; st.rerun()

alle_kategorien = sorted(df["kategorie"].dropna().str.strip().unique().tolist())
kategorie_labels_liste = [KATEGORIE_LABELS.get(k,k) for k in alle_kategorien]
label_zu_key = {v:k for k,v in KATEGORIE_LABELS.items()}

einschliessen_labels = st.sidebar.multiselect("Kategorie einschließen", options=kategorie_labels_liste,
    default=[], placeholder="Alle anzeigen", key="einschliessen")
einschliessen_keys = [label_zu_key.get(l,l) for l in einschliessen_labels]

ausschliessen_labels = st.sidebar.multiselect("Kategorie ausschließen", options=kategorie_labels_liste,
    default=["Kirche"], placeholder="Nichts ausschließen", key="ausschliessen")
ausschliessen_keys = [label_zu_key.get(l,l) for l in ausschliessen_labels]

alle_anlagen = sorted(set(t.strip() for typen in df["anlagetyp"].dropna()
    for t in str(typen).split(",") if t.strip()))
anlage_labels = [ANLAGETYP_ICONS.get(a,a) for a in alle_anlagen]
anlage_label_zu_key = {v:k for k,v in ANLAGETYP_ICONS.items()}
ausgewaehlte_anlage_labels = st.sidebar.multiselect("Art der Hörunterstützung", options=anlage_labels,
    default=[], placeholder="Alle Arten der Hörunterstützung anzeigen", key="anlagetyp_filter")
ausgewaehlte_anlagen = [anlage_label_zu_key.get(l,l) for l in ausgewaehlte_anlage_labels]

df_filtered = df.copy()
suche_key  = f"suche_{st.session_state['suche_counter']}"
suche_wert = st.session_state.get(suche_key,"").strip()
if suche_wert:
    df_filtered = df_filtered[
        df_filtered["name"].str.contains(suche_wert,case=False,na=False) |
        df_filtered["adresse"].str.contains(suche_wert,case=False,na=False) |
        df_filtered["stadtteil"].str.contains(suche_wert,case=False,na=False)]
if einschliessen_keys:
    df_filtered = df_filtered[df_filtered["kategorie"].str.strip().isin(einschliessen_keys)]
if ausschliessen_keys:
    df_filtered = df_filtered[~df_filtered["kategorie"].str.strip().isin(ausschliessen_keys)]
if ausgewaehlte_anlagen:
    df_filtered = df_filtered[df_filtered["anlagetyp"].apply(
        lambda x: any(t in ausgewaehlte_anlagen for t in get_anlagetyp_list(x)) if pd.notna(x) else False)]

st.sidebar.markdown("---")
st.sidebar.markdown("**Legende**")
for kat in sorted(df_filtered["kategorie"].dropna().str.strip().unique()):
    st.sidebar.markdown(
        f'<span style="color:{hex_farbe(kat)};font-size:18px;">●</span> **{KATEGORIE_LABELS.get(kat,kat)}**',
        unsafe_allow_html=True)
st.sidebar.markdown("---")
st.sidebar.caption(f"{len(df_filtered)} Orte angezeigt von {len(df)} gesamt")

# --- Buttons ---
btn_col1, btn_col2, _ = st.columns([2,2,6])
with btn_col1:
    if st.button("➕ Ort vorschlagen", type="secondary", use_container_width=True): dialog_neuer_ort()
with btn_col2:
    if st.button("💡 Feedback & Ideen", type="secondary", use_container_width=True): dialog_feedback()

# --- Karte ---
karte = folium.Map(location=[53.55,10.0], zoom_start=11, tiles="CartoDB positron")
for _, row in df_filtered.iterrows():
    kat = str(row.get("kategorie","")).strip().lower()
    folium.Marker(
        location=[row["lat"],row["lon"]],
        popup=folium.Popup(build_popup(row), max_width=280),
        tooltip=row.get("name",""),
        icon=folium.Icon(color=folium_farbe(kat), icon=folium_icon(kat), prefix="fa"),
    ).add_to(karte)

karten_output = st_folium(karte, width="60%", height=500, returned_objects=["last_object_clicked_tooltip"])
neuer_klick = karten_output.get("last_object_clicked_tooltip")
if neuer_klick and neuer_klick != st.session_state["angeklickter_ort"]:
    st.session_state["angeklickter_ort"] = neuer_klick; st.rerun()

# --- Kommentarbereich ---
if not angeklickter_ort:
    kommentare_alle = load_kommentare()
    if not kommentare_alle.empty:
        moderierte = kommentare_alle[
            kommentare_alle["moderiert"].str.strip().str.lower() == "ja"
        ].sort_values("datum", ascending=False).head(6)
        if not moderierte.empty:
            st.markdown("---")
            st.markdown("### 💬 Neueste Kommentare der Community")
            ort_id_zu_name = dict(zip(df["ort_id"].astype(str), df["name"].astype(str)))
            for _, k in moderierte.iterrows():
                ort_id_k   = val(k.get("ort_id"))
                ort_name   = ort_id_zu_name.get(ort_id_k, ort_id_k)
                ort_row    = df[df["ort_id"].astype(str) == ort_id_k]
                farbe      = hex_farbe(val(ort_row.iloc[0].get("kategorie"))) if not ort_row.empty else "#adb5bd"
                autor      = val(k.get("autor_name")) or "Anonym"
                datum      = val(k.get("datum"))
                text       = val(k.get("kommentar"))
                ampel      = val(k.get("ampel"))
                geraet     = val(k.get("geraet"))
                anlagen    = val(k.get("verwendete_anlage"))
                ampel_label = AMPEL_OPTIONEN.get(ampel, "")
                ampel_farbe = AMPEL_FARBEN.get(ampel, "#adb5bd")
                meta_parts  = []
                if geraet:  meta_parts.append(f"🦻 {geraet}")
                if anlagen:
                    anlagen_labels = ", ".join([ANLAGETYP_ICONS.get(a.strip(), a.strip()) for a in anlagen.split(",")])
                    meta_parts.append(f"📡 {anlagen_labels}")
                meta_html = " · ".join(meta_parts)
                st.markdown(
                    f'<div style="border-left:4px solid {ampel_farbe};padding-left:10px;margin-bottom:12px;">'
                    f'<span style="color:{farbe};font-weight:bold;">{ort_name}</span> · '
                    f'<b>{autor}</b> · <span style="color:#888;font-size:12px;">{datum}</span><br>'
                    f'<span style="color:{ampel_farbe};font-weight:bold;">{ampel_label}</span><br>'
                    f'<span style="color:#888;font-size:12px;">{meta_html}</span><br>'
                    f'{text}</div>', unsafe_allow_html=True)

if angeklickter_ort:
    treffer = df[df["name"] == angeklickter_ort]
    if not treffer.empty:
        row    = treffer.iloc[0]
        ort_id = val(row.get("ort_id"))
        farbe  = hex_farbe(val(row.get("kategorie")))

        st.markdown("---")
        st.markdown(f'<h3 style="color:{farbe}">💬 Kommentare zu {angeklickter_ort}</h3>', unsafe_allow_html=True)
        tab_lesen, tab_schreiben = st.tabs(["📖 Kommentare lesen","✏️ Kommentar schreiben"])

        with tab_lesen:
            kommentare = load_kommentare()
            if kommentare.empty:
                st.caption("Noch keine freigeschalteten Kommentare für diesen Ort.")
            else:
                kommentare_ort = kommentare[
                    (kommentare["ort_id"] == ort_id) &
                    (kommentare["moderiert"].str.strip().str.lower() == "ja")
                ].sort_values("datum", ascending=False)
                if kommentare_ort.empty:
                    st.caption("Noch keine freigeschalteten Kommentare für diesen Ort.")
                else:
                    for _, k in kommentare_ort.iterrows():
                        autor   = val(k.get("autor_name")) or "Anonym"
                        datum   = val(k.get("datum"))
                        text    = val(k.get("kommentar"))
                        ampel   = val(k.get("ampel"))
                        geraet  = val(k.get("geraet"))
                        anlagen = val(k.get("verwendete_anlage"))
                        ampel_label = AMPEL_OPTIONEN.get(ampel, "")
                        ampel_farbe = AMPEL_FARBEN.get(ampel, "#adb5bd")
                        meta_parts  = []
                        if geraet:  meta_parts.append(f"🦻 {geraet}")
                        if anlagen:
                            anlagen_labels = ", ".join([ANLAGETYP_ICONS.get(a.strip(), a.strip()) for a in anlagen.split(",")])
                            meta_parts.append(f"📡 {anlagen_labels}")
                        meta_html = " · ".join(meta_parts)
                        st.markdown(
                            f'<div style="border-left:4px solid {ampel_farbe};padding-left:10px;margin-bottom:12px;">'
                            f'<b>{autor}</b> · <span style="color:#888;font-size:12px;">{datum}</span><br>'
                            f'<span style="color:{ampel_farbe};font-weight:bold;">{ampel_label}</span><br>'
                            f'<span style="color:#888;font-size:12px;">{meta_html}</span><br>'
                            f'{text}</div>', unsafe_allow_html=True)

        with tab_schreiben:
            st.caption("Kommentare werden nach Prüfung freigeschaltet.")
            if "form_counter" not in st.session_state:
                st.session_state["form_counter"] = 0
            with st.form(key=f"kommentar_form_{ort_id}_{st.session_state['form_counter']}", clear_on_submit=True):
                ampel_wahl = st.radio(
                    "Wie hat die Höranlage funktioniert? *",
                    options=list(AMPEL_OPTIONEN.keys()),
                    format_func=lambda x: AMPEL_OPTIONEN[x],
                )
                alle_anlage_labels = [v for k,v in ANLAGETYP_ICONS.items() if k != "anderes"]
                verwendete_wahl = st.multiselect("Welche Art(en) der Hörunterstützung hast du verwendet? *",
                                                  options=alle_anlage_labels + ["➕ Anderes"])
                anlage_icon_zu_key = {v:k for k,v in ANLAGETYP_ICONS.items()}
                verwendete_keys = [anlage_icon_zu_key.get(a,a) for a in verwendete_wahl if a != "➕ Anderes"]
                anlage_sonstige = ""
                if "➕ Anderes" in verwendete_wahl:
                    anlage_sonstige = st.text_input("Welche Arten der Hörunterstützung? Bitte beschreiben:", key="anlage_sonstige_kommentar")
                    if anlage_sonstige.strip():
                        verwendete_keys.append(f"anderes: {anlage_sonstige.strip()}")
                geraet_wahl     = st.selectbox("Mit welchem Gerät hast du zugehört? *", options=GERAET_OPTIONEN)
                autor_input     = st.text_input("Dein Name (optional)", placeholder="Anonym")
                kommentar_input = st.text_area("Kommentar", placeholder="Deine Erfahrung...", max_chars=1000)
                if st.form_submit_button("Absenden"):
                    if not verwendete_keys:
                        st.warning("Bitte wähle mindestens eine Art der Hörunterstützung aus.")
                    elif not geraet_wahl:
                        st.warning("Bitte wähle ein Gerät aus.")
                    else:
                        save_kommentar(ort_id=ort_id, autor=autor_input,
                                       kommentar=kommentar_input.strip(), ampel=ampel_wahl,
                                       verwendete_anlage=verwendete_keys, geraet=geraet_wahl)
                        clear_kommentare_cache()
                        st.session_state["form_counter"] = st.session_state.get("form_counter", 0) + 1
                        st.success("Danke! Dein Kommentar wird nach Prüfung freigeschaltet.")

# --- Impressum & Footer ---
st.markdown("---")
st.markdown("#### Impressum")

ft_col1, ft_col2 = st.columns([1, 2])

with ft_col1:
    st.markdown("##### 🦻 Hörkompass")
    st.markdown("Leonie & Marina \nHamburg  \n📧 leonie@vonberlin.de")

with ft_col2:
    st.markdown("##### 📋 Rechtliches")
    st.caption("Dieses Projekt verfolgt keine kommerziellen Zwecke. Es dient der barrierefreien Information für Schwerhörige.")
    st.markdown("**Quellenangabe**  \nAusgangsdaten teilweise basierend auf dem [Verzeichnis des Bund der Schwerhörigen e.V. Hamburg](https://www.bds-hh.de) (Stand Mai 2020), eigenständig und durch die Community geprüft und erweitert.")
    st.markdown("**Haftungsausschluss**  \nAlle Angaben ohne Gewähr. Trotz sorgfältiger Prüfung können Angaben veraltet oder unvollständig sein. Bei Fehlern freuen wir uns über eine Meldung über den Feedback-Button.")
    st.markdown("**Datenschutz**  \nDiese Seite speichert keine personenbezogenen Daten außer freiwillig hinterlassenen Kommentaren. Es werden keine Cookies gesetzt und keine Nutzungsdaten weitergegeben.")

# with ft_col3:
#     st.markdown("##### 🤝 Partner")
#     try:
#         st.image("logo_doa.png", width=120)
#     except Exception:
#         pass
#     st.markdown("**Deaf Ohr Alive (DOA) Nord**  \nTeil von DOA  \n[www.deaf-ohr-alive.de](https://www.deaf-ohr-alive.de)")

st.caption("Hörkompass · 2026")
