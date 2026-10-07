# Council

Council is a private, multi-perspective decision-support prototype for career and education choices. It analyzes a dilemma through Logic, Risk, Human, and Growth perspectives, then gives a grounded verdict with a confidence score.

The prototype includes conservative crisis detection with category-specific support guidance, per-user SQLite scoping, guest mode, optional Google OIDC, history, journal safety checks, feedback, charts, JSON/PDF export, daily request limits, retry/fallback model handling, and data deletion.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Without `GEMINI_API_KEY`, Council uses a clearly labelled deterministic demo response. Set `GEMINI_API_KEY` to enable structured Gemini responses. API keys remain server-side.

Model reliability uses three attempts with exponential backoff on the primary model, then three attempts on `GEMINI_FALLBACK_MODEL` (default `gemini-2.0-flash-lite`) before showing the local demo response.

The default daily request cap is 20 and can be changed with the `DAILY_REQUEST_LIMIT` Streamlit secret. The app supports guest use locally. For production, configure Streamlit OIDC (`.streamlit/secrets.toml`) with `OAUTH_CLIENT_ID` and the standard Google provider settings, then add per-user database scoping before multi-user deployment.

Run tests with `pytest`.

The test suite covers schema validation, reviewed crisis phrases and normal phrases, region fallback, vague-input handling, user isolation, feedback comments, and request counting. Start the app with `streamlit run app.py` and verify the local endpoint before deployment.

For local configuration, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and replace placeholders. The example is intentionally excluded from the secrets ignore rule only because it contains no credentials; never commit the real file.
