# Promo Delivery V5 — Online Ready

Pare pou GitHub + Render.

GitHub:
1. Kreye repository `promo-delivery`.
2. Dezip package sa.
3. Upload TOUT fichye ak folders ki anndan li nan repository a.
4. Pa upload ZIP la kòm sèl fichye.

Render Web Service:
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`
- Health: `/health`

Database:
- App la itilize PostgreSQL si `DATABASE_URL` egziste.
- Pou tès lokal, li itilize SQLite otomatikman.
- Sou Render, konekte yon Render Postgres database epi mete Internal Database URL li kòm `DATABASE_URL`.

Paj yo:
- Client: `/`
- Admin: `/admin`
- Livreur: `/driver`
