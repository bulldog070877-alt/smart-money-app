"""
Email/password login, backed by a `users` table in the same Neon Postgres
database used for the price cache. Session persistence (so refreshing the
page doesn't log you out) is handled by streamlit-authenticator via a signed
browser cookie - the signing key lives in AUTH_COOKIE_KEY (Streamlit secrets).
"""
import re

import psycopg2
import streamlit as st
import streamlit_authenticator as stauth

from data_store import connection_string

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now()
)
"""

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

LOGIN_FIELDS = {'Form name': 'Login', 'Username': 'Email', 'Password': 'Password', 'Login': 'Login'}


def _get_conn():
    conn = psycopg2.connect(connection_string(), connect_timeout=10)
    with conn.cursor() as cur:
        cur.execute(_CREATE_TABLE_SQL)
    conn.commit()
    return conn


def load_credentials():
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT email, name, password_hash FROM users")
            rows = cur.fetchall()
    finally:
        conn.close()
    return {
        'usernames': {
            email: {'email': email, 'name': name, 'password': password_hash}
            for email, name, password_hash in rows
        }
    }


def create_user(email, name, password):
    email = email.strip().lower()
    name = name.strip()
    if not _EMAIL_RE.match(email):
        raise ValueError("Enter a valid email address.")
    if not name:
        raise ValueError("Enter your name.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")

    password_hash = stauth.Hasher.hash(password)
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO users (email, name, password_hash) VALUES (%s, %s, %s)",
                    (email, name, password_hash),
                )
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                raise ValueError("That email is already registered.")
        conn.commit()
    finally:
        conn.close()


def require_login():
    """Gate the whole app behind login. Renders login + signup forms and
    calls st.stop() if the user isn't authenticated yet. Returns the
    Authenticate instance (for rendering a logout button) once logged in."""
    credentials = load_credentials()
    authenticator = stauth.Authenticate(
        credentials,
        cookie_name='smart_money_auth',
        cookie_key=st.secrets["AUTH_COOKIE_KEY"],
        cookie_expiry_days=30,
        auto_hash=False,
    )

    authenticator.login(fields=LOGIN_FIELDS)

    if st.session_state.get('authentication_status'):
        return authenticator

    st.title("📈 Smart Money Strategy")

    if st.session_state.get('authentication_status') is False:
        st.error("Email or password is incorrect.")

    with st.expander("New here? Create an account"):
        with st.form("signup_form", clear_on_submit=True):
            name = st.text_input("Name")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            confirm = st.text_input("Confirm password", type="password")
            if st.form_submit_button("Sign up"):
                if password != confirm:
                    st.error("Passwords don't match.")
                else:
                    try:
                        create_user(email, name, password)
                        st.success("Account created — log in above.")
                    except ValueError as e:
                        st.error(str(e))

    st.stop()
