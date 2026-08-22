import sys
import os
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager

# Configuración robusta del PATH para Render y local
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from src.core.orquestador import PipelineOrquestador
from src.db_repository import RepositorioDiccionario


repositorio: RepositorioDiccionario | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global repositorio

    is_dev = (
        os.environ.get("DEBUG", "").lower() == "true"
        or os.environ.get("LOCAL_DEV", "").lower() == "true"
    )
    db_url = os.environ.get("DATABASE_URL")

    if not db_url:
        if is_dev:
            print("[API] WARNING: DATABASE_URL not set. Falling back to JSON mode in development.")
            repositorio = RepositorioDiccionario()
            repositorio._inicializar_json()
        else:
            raise RuntimeError(
                "CRITICAL ERROR: DATABASE_URL environment variable is missing or empty. "
                "Halt startup in production to prevent data anomalies."
            )
    else:
        repositorio = RepositorioDiccionario()
        try:
            await repositorio.inicializar()
        except Exception as e:
            if is_dev:
                print(f"[API] WARNING: Database connection failed: {e}. Falling back to JSON mode in development.")
                repositorio = RepositorioDiccionario()
                repositorio._inicializar_json()
            else:
                raise RuntimeError(
                    f"CRITICAL ERROR: Database connection failed: {e}. "
                    "Fail-fast active in production to prevent data anomalies."
                ) from e

    yield

    if repositorio:
        await repositorio.cerrar()
        repositorio = None


app = FastAPI(
    title="API de Inteligencia Financiera y Homologación",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "repositorio": repositorio is not None}


@app.post("/api/v1/analisis/procesar")
async def procesar_analisis(
    file_balance: UploadFile = File(...),
    file_carpeta: UploadFile | None = File(None),
    giro_empresa: str = Form(...),
):
    if repositorio is None:
        raise HTTPException(status_code=503, detail="Repositorio no disponible")

    if file_carpeta is not None and file_carpeta.filename:
        if not file_carpeta.filename.endswith(".pdf"):
            raise HTTPException(status_code=400, detail="file_carpeta debe ser un archivo PDF")
    if not file_balance.filename or not file_balance.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="file_balance debe ser un archivo PDF")

    tmp_carpeta = None
    tmp_balance = None

    try:
        if file_carpeta is not None and file_carpeta.filename:
            tmp_carpeta = _save_upload(file_carpeta)
        tmp_balance = _save_upload(file_balance)

        orquestador = PipelineOrquestador(repositorio)
        resultado = await orquestador.procesar_analisis_completo(
            ruta_carpeta=tmp_carpeta,
            ruta_balance=tmp_balance,
            giro_empresa=giro_empresa,
        )

        return resultado.to_dict()

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno al procesar el análisis: {e}",
        )
    finally:
        if tmp_carpeta:
            Path(tmp_carpeta).unlink(missing_ok=True)
        if tmp_balance:
            Path(tmp_balance).unlink(missing_ok=True)


def _save_upload(file: UploadFile) -> str:
    suffix = Path(file.filename).suffix if file.filename else ".tmp"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        content = file.file.read()
        tmp.write(content)
        tmp.flush()
    finally:
        tmp.close()
    return tmp.name
