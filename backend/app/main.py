from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.migrate import run_migrations

# सर्व्हर चालू होतोवेळी (startup ला) डेटाबेस मायग्रेशन आपोआप होण्यासाठी
@asynccontextmanager
async def lifespan(app: FastAPI):
    # स्टार्टअप वेळी मायग्रेशन रन करा
    try:
        run_migrations()
    except Exception as e:
        print(f"Migration error: {e}")
    yield

app = FastAPI(lifespan=lifespan)

# बाकीचा तुझा मूळ कोड इथे खाली असेल (किंवा जसाच्या तसा ठेव)
@app.get("/")
def read_root():
    return {"message": "Gov Jobs Tracker API is running"}