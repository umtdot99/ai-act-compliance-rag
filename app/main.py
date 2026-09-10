from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.retrieval import Retriever
from app.generate import answer

state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["retriever"] = Retriever()    
    yield
    state.clear()

app = FastAPI(lifespan=lifespan)


class AskRequest(BaseModel):
    question: str
    k: int = 5

@app.get("/health")
def health():
    r = state.get("retriever")
    if r is None:
        raise HTTPException(status_code=503, detail="retriever not ready")
    return {"status": "ready", "chunks": len(r.chunk)}


@app.post("/ask")
def ask(req: AskRequest):
    r = state["retriever"]
    top_k = r.search(req.question, req.k)
    context = r.build_context(top_k)
    text = answer(req.question, context)
    return {"answer": text, "chunks": [cid for cid, _ in top_k]}