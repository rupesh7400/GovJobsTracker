from fastapi import FastAPI
from app.migrate import run_migrations

# सर्व्हर चालू होताच डेटाबेस मायग्रेशन रन करा
try:
    run_migrations()
except Exception as e:
    print(f"Migration error: {e}")

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Gov Jobs Tracker API is running"}