import json
import uuid
import streamlit as st

from council import analyze
from db import make_db, save_decision, list_decisions, delete_all, add_journal_entry, list_journal_entries, set_feedback, requests_today, decision_metrics, get_settings, save_settings
from export import as_json, as_pdf
from safety import detect_crisis, support_card

def secret(name: str, default=""):
    """Read an optional Streamlit secret without breaking local guest mode."""
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


st.set_page_config(page_title="Council", page_icon="⚖️", layout="wide")
st.title("⚖️ Council")
st.caption("A private, multi-perspective decision-support tool — not a professional or emergency service.")
engine = make_db(secret("DATABASE_PATH", "council.db"))
DAILY_LIMIT = int(secret("DAILY_REQUEST_LIMIT", 20))

# Streamlit OIDC is optional: local users can continue in guest mode.
oidc_enabled = bool(secret("OAUTH_CLIENT_ID", ""))
if oidc_enabled and hasattr(st, "user") and not st.user.is_logged_in:
    st.info("Sign in to keep your decisions associated with your account, or continue as a guest.")
    if st.button("Sign in with Google") and hasattr(st, "login"):
        st.login("google")
elif oidc_enabled and hasattr(st, "user") and st.user.is_logged_in:
    st.caption(f"Signed in as {st.user.get('email', 'user')}")

user_id = "guest"
if oidc_enabled and hasattr(st, "user") and st.user.is_logged_in:
    user_id = str(st.user.get("email", "authenticated-user"))
else:
    if "guest_id" not in st.query_params:
        st.query_params["guest_id"] = uuid.uuid4().hex
    user_id = "guest:" + st.query_params["guest_id"]

with st.sidebar:
    st.header("Settings")
    settings = get_settings(engine, user_id)
    country = st.text_input("Country code (IN, US, or GB)", value=settings.country, max_chars=2)
    with st.expander("Profile"):
        profile_name = st.text_input("Name", value=settings.name, key="profile_name")
        profile_city = st.text_input("City (optional)", value=settings.city, key="profile_city")
        location_enabled = st.checkbox("Use location for safety support", value=bool(settings.location_enabled))
        emergency_contact = st.text_input("Trusted emergency contact", value=settings.emergency_contact)
        if st.button("Save settings"):
            save_settings(engine, user_id, name=profile_name, country=country, city=profile_city, emergency_contact=emergency_contact, location_enabled=int(location_enabled))
            st.success("Settings saved.")
    st.caption("Privacy: data is stored in the configured SQLite database and sent to the model provider only when you submit a dilemma. You can delete saved decisions below.")
    if st.button("Delete all my decisions", type="secondary"):
        delete_all(engine, user_id); st.success("Your saved decisions and reflections were deleted.")

tab_new, tab_history = st.tabs(["New decision", "History"])
with tab_new:
    category = st.selectbox("Category", ["Career", "Education", "Money", "Relationships", "Other"])
    dilemma = st.text_area("What are you deciding?", placeholder="Describe the situation, options, and what matters most…", height=160)
    if st.button("Ask Council", type="primary"):
        safety = detect_crisis(dilemma)
        if safety.is_crisis:
            st.error(f"Safety alert ({safety.category})")
            card = support_card(country, safety.category or "cybercrime or extortion", emergency_contact)
            st.info(f"**{card['title']}**\n\n{safety.message}\n\n{card['body']}")
        elif requests_today(engine, user_id) >= DAILY_LIMIT:
            st.warning(f"Daily request limit reached ({DAILY_LIMIT}). Try again tomorrow.")
        elif not dilemma.strip():
            st.warning("Please describe your dilemma first.")
        else:
            response = analyze(dilemma, category)
            if response.is_fallback:
                st.error(response.error_message or "This is a local fallback preview and was not saved to history.")
            else:
                save_decision(engine, dilemma, category, response.model_dump_json(), user_id)
            st.session_state["response"] = response
            st.session_state["request"] = (dilemma, category)
    response = st.session_state.get("response")
    if response:
        st.subheader("Grounded verdict")
        st.write(response.verdict); st.metric("Confidence", f"{response.confidence:.0%}")
        if response.caution_note: st.warning(response.caution_note)
        if response.clarifying_question: st.info("Clarifying question: " + response.clarifying_question)
        cols = st.columns(4)
        for col, label in zip(cols, ["Logic", "Risk", "Human", "Growth"]):
            with col:
                p = getattr(response, label.lower()); st.subheader(label); st.write(p.summary); st.write(p.advice); st.caption("Risk: " + p.risk_note)
        dilemma0, category0 = st.session_state["request"]
        st.download_button("Download JSON", as_json(dilemma0, category0, response), "council-decision.json", "application/json")
        st.download_button("Download PDF", as_pdf(dilemma0, category0, response), "council-decision.pdf", "application/pdf")
        st.caption("Was this helpful?")
        feedback_comment = st.text_input("Optional feedback", max_chars=2000, key="feedback_comment")
        f1, f2 = st.columns(2)
        current = list_decisions(engine, 1, user_id)
        if current:
            if f1.button("Helpful", key="helpful"): set_feedback(engine, current[0].id, 1, feedback_comment); st.success("Thanks for the feedback.")
            if f2.button("Not helpful", key="not_helpful"): set_feedback(engine, current[0].id, 0, feedback_comment); st.success("Thanks for the feedback.")

with tab_history:
    history_items = list_decisions(engine, user_id=user_id)
    for item in history_items:
        with st.expander(f"{item.category} — {item.dilemma[:80]}"):
            st.caption(item.created_at.strftime("%Y-%m-%d %H:%M UTC"))
            saved = json.loads(item.response_json)
            st.write(saved.get("verdict", "")); st.metric("Confidence", f"{saved.get('confidence', 0):.0%}")
            columns = st.columns(4)
            for column, label in zip(columns, ["logic", "risk", "human", "growth"]):
                with column:
                    perspective = saved.get(label, {})
                    st.subheader(label.title()); st.write(perspective.get("summary", "")); st.write(perspective.get("advice", "")); st.caption("Risk: " + perspective.get("risk_note", ""))
    metrics = decision_metrics(engine, user_id)
    if metrics["rated"]:
        st.metric("Helpful rating", f"{metrics['helpful'] / metrics['rated']:.0%}")
    if list_decisions(engine, user_id=user_id):
        st.subheader("Decision categories")
        try:
            import plotly.express as px
            history = list_decisions(engine, user_id=user_id)
            data = [{"category": item.category} for item in history]
            st.plotly_chart(px.histogram(data, x="category"), use_container_width=True)
            trend = []
            for item in reversed(history):
                payload = json.loads(item.response_json)
                trend.append({"date": item.created_at, "confidence": payload.get("confidence", 0), "helpful": item.feedback})
            st.plotly_chart(px.line(trend, x="date", y="confidence", markers=True, title="Confidence over time"), use_container_width=True)
            rated = [point for point in trend if point["helpful"] is not None]
            if rated:
                st.plotly_chart(px.scatter(rated, x="date", y="helpful", title="Feedback over time", labels={"helpful": "Helpful (1=yes, 0=no)"}), use_container_width=True)
        except ImportError:
            st.caption("Install Plotly to view charts.")

st.divider()
st.subheader("Daily reflection")
journal_text = st.text_area("What did you learn today?", height=80, key="journal")
if st.button("Save reflection") and journal_text.strip():
    journal_safety = detect_crisis(journal_text)
    if journal_safety.is_crisis:
        card = support_card(country, journal_safety.category or "self-harm", emergency_contact)
        st.error(f"**{card['title']}**\n\n{card['body']}")
    else:
        add_journal_entry(engine, journal_text.strip(), user_id); st.success("Reflection saved privately.")
for entry in list_journal_entries(engine, 5, user_id):
    st.caption(f"{entry.created_at.strftime('%Y-%m-%d')}: {entry.text}")
