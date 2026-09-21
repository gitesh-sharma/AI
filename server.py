import os
import re
import json
import math
import sqlite3
import subprocess
import threading
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pypdf import PdfReader
from docx import Document

load_dotenv()
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MODELS = ROOT / "models"
RUNTIME = ROOT / "runtime"
DATA.mkdir(exist_ok=True)
MODELS.mkdir(exist_ok=True)
RUNTIME.mkdir(exist_ok=True)
DB = DATA / "sns_ai.sqlite3"
HOST = os.getenv("SNS_AI_HOST", "127.0.0.1")
PORT = int(os.getenv("SNS_AI_PORT", "8787"))
LLM_URL = os.getenv("SNS_AI_LLM_URL", "http://127.0.0.1:8080").rstrip("/")
MODEL = os.getenv("SNS_AI_MODEL", str(MODELS / "main.gguf"))
CONTEXT = int(os.getenv("SNS_AI_CONTEXT", "4096"))
AUTO_START = os.getenv("SNS_AI_AUTO_START", "1") == "1"
MAX_DOC_CHARS = int(os.getenv("SNS_AI_MAX_DOC_CHARS", "120000"))
COMFY_URL = os.getenv("SNS_AI_COMFY_URL", "").rstrip("/")

app = FastAPI(title="SNS AI", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(ROOT / "app" / "static")), name="static")
llama_process = None
llama_lock = threading.Lock()


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS conversations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL DEFAULT 'New chat',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      conversation_id INTEGER NOT NULL,
      role TEXT NOT NULL,
      content TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS documents (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      mime TEXT,
      content TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """)
    c.commit(); c.close()


@app.on_event("startup")
def startup():
    init_db()
    if AUTO_START:
        start_llama_if_possible()


def llama_binary():
    env = os.getenv("SNS_AI_LLAMA_SERVER")
    if env:
        p = Path(env)
        if not p.is_absolute(): p = ROOT / p
        if p.exists(): return str(p)
    names = ["llama-server.exe", "llama-server"]
    for name in names:
        p = RUNTIME / name
        if p.exists(): return str(p)
    return "llama-server"


def start_llama_if_possible():
    global llama_process
    if llama_process and llama_process.poll() is None:
        return
    if not Path(MODEL).exists():
        return
    with llama_lock:
        if llama_process and llama_process.poll() is None: return
        try:
            llama_process = subprocess.Popen([
                llama_binary(), "-m", MODEL,
                "--host", "127.0.0.1", "--port", "8080",
                "-c", str(CONTEXT), "--no-webui"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            llama_process = None


def extract_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        import io
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((p.extract_text() or "") for p in reader.pages)
    if suffix == ".docx":
        import io
        d = Document(io.BytesIO(data))
        return "\n".join(p.text for p in d.paragraphs)
    if suffix in {".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".json", ".csv", ".xml", ".yml", ".yaml"}:
        return data.decode("utf-8", errors="replace")
    raise ValueError("Unsupported file type. Use PDF, DOCX, TXT, MD or common code/text files.")


def tokens(s):
    return re.findall(r"[a-zA-Z0-9_\u0900-\u097F]{2,}", s.lower())


def retrieve(query: str, limit=4):
    q = set(tokens(query))
    c = db(); rows = c.execute("SELECT id,name,content FROM documents").fetchall(); c.close()
    scored=[]
    for r in rows:
        ts=tokens(r["content"])
        if not ts: continue
        common=len(q & set(ts))
        if common:
            scored.append((common/math.sqrt(len(ts)), r))
    scored.sort(key=lambda x:x[0], reverse=True)
    return [r for _,r in scored[:limit]]


class ChatIn(BaseModel):
    conversation_id: Optional[int] = None
    message: str
    mode: str = "chat"
    use_documents: bool = True
    temperature: float = 0.7


class ToolIn(BaseModel):
    tool: str
    input: str


class ImageIn(BaseModel):
    prompt: str


@app.get("/")
def index():
    return FileResponse(ROOT / "app" / "static" / "index.html")


@app.get("/api/health")
def health():
    alive=False
    try:
        r=httpx.get(f"{LLM_URL}/health", timeout=1.5)
        alive=r.status_code == 200
    except Exception: pass
    return {"ok":True,"llm":alive,"model":Path(MODEL).name,"model_present":Path(MODEL).exists()}


@app.get("/api/conversations")
def conversations():
    c=db(); rows=c.execute("SELECT * FROM conversations ORDER BY updated_at DESC").fetchall(); c.close()
    return [dict(r) for r in rows]


@app.get("/api/conversations/{cid}")
def conversation(cid:int):
    c=db(); conv=c.execute("SELECT * FROM conversations WHERE id=?",(cid,)).fetchone(); msgs=c.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY id",(cid,)).fetchall(); c.close()
    if not conv: raise HTTPException(404,"Conversation not found")
    return {"conversation":dict(conv),"messages":[dict(x) for x in msgs]}


@app.post("/api/chat")
async def chat(inp: ChatIn):
    c=db()
    cid=inp.conversation_id
    if not cid:
        cur=c.execute("INSERT INTO conversations(title) VALUES(?)",(inp.message[:60] or "New chat",)); cid=cur.lastrowid
    c.execute("INSERT INTO messages(conversation_id,role,content) VALUES(?,?,?)",(cid,"user",inp.message)); c.commit()
    history=c.execute("SELECT role,content FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 12",(cid,)).fetchall(); c.close()
    history=list(reversed(history))
    system="You are SNS AI, a private offline assistant. Be accurate, concise, and transparent about uncertainty. Never claim internet access."
    if inp.mode=="coding": system += " You are in coding mode. Return practical, runnable code and explain key changes briefly."
    if inp.use_documents:
        docs=retrieve(inp.message)
        if docs:
            context="\n\n".join(f"SOURCE: {d['name']}\n{d['content'][:8000]}" for d in docs)
            system += "\nUse the following local documents when relevant. Do not invent facts not present in them:\n"+context
    messages=[{"role":"system","content":system}]+[{"role":x["role"],"content":x["content"]} for x in history]
    payload={"messages":messages,"temperature":max(0,min(1.5,inp.temperature)),"stream":False}
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            r=await client.post(f"{LLM_URL}/v1/chat/completions",json=payload)
            r.raise_for_status(); data=r.json()
        answer=data["choices"][0]["message"]["content"]
    except Exception as e:
        raise HTTPException(503,f"Local model unavailable. Start llama-server or place a GGUF model in models/. Details: {e}")
    c=db(); c.execute("INSERT INTO messages(conversation_id,role,content) VALUES(?,?,?)",(cid,"assistant",answer)); c.execute("UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?",(cid,)); c.commit(); c.close()
    return {"conversation_id":cid,"answer":answer}


@app.post("/api/documents")
async def upload(files:list[UploadFile]=File(...)):
    out=[]
    for f in files:
        data=await f.read()
        try: text=extract_text(f.filename,data)[:MAX_DOC_CHARS]
        except ValueError as e: raise HTTPException(400,str(e))
        if not text.strip(): raise HTTPException(400,f"No text extracted from {f.filename}")
        c=db(); cur=c.execute("INSERT INTO documents(name,mime,content) VALUES(?,?,?)",(f.filename,f.content_type,text)); c.commit(); did=cur.lastrowid; c.close()
        out.append({"id":did,"name":f.filename,"chars":len(text)})
    return {"documents":out}


@app.get("/api/documents")
def documents():
    c=db(); rows=c.execute("SELECT id,name,mime,length(content) chars,created_at FROM documents ORDER BY id DESC").fetchall(); c.close(); return [dict(r) for r in rows]


@app.post("/api/tools")
def tools(inp:ToolIn):
    if inp.tool=="calculator":
        if not re.fullmatch(r"[0-9+\-*/().,% ^]+",inp.input.strip()): raise HTTPException(400,"Only numeric calculator expressions are allowed.")
        expr=inp.input.replace("^","**").replace("%","/100")
        try: return {"result":str(eval(expr,{"__builtins__":{}},{}))}
        except Exception as e: raise HTTPException(400,str(e))
    if inp.tool=="json":
        try: return {"result":json.dumps(json.loads(inp.input),indent=2,ensure_ascii=False)}
        except Exception as e: raise HTTPException(400,str(e))
    if inp.tool=="stats":
        words=tokens(inp.input); return {"characters":len(inp.input),"words":len(words),"lines":len(inp.input.splitlines())}
    raise HTTPException(400,"Unknown tool")


@app.post("/api/image/generate")
async def image_generate(inp: ImageIn):
    """Optional local image generation bridge. Requires ComfyUI running locally and SNS_AI_COMFY_URL set."""
    if not COMFY_URL:
        raise HTTPException(503, "Local image generation is optional. Install/run ComfyUI locally and set SNS_AI_COMFY_URL.")
    raise HTTPException(501, "ComfyUI bridge is intentionally not tied to a specific workflow JSON in this starter. Configure your local workflow and add its API payload here.")


@app.get("/api/config")
def config():
    return {"name":"SNS AI","version":"0.1.0","llm_url":LLM_URL,"model":Path(MODEL).name,"comfy":bool(COMFY_URL)}
