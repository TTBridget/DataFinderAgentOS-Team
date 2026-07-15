from app.models.db import get_connection
rows = get_connection().execute("SELECT id,name,type,api_url,card_type FROM digital_employees").fetchall()
for r in rows:
    print(dict(r))
