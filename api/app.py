from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from api.routes import router

app = FastAPI(
    title="RD Obras — WhatsApp Report",
    description=(
        "Painel de controle do serviço de relatórios diários de obra.\n\n"
        "Use `/report/trigger` para disparar um envio imediato, "
        "`/status` para ver o estado do scheduler e `/report/stats` "
        "para o histórico de execuções."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(router)


@app.get("/", include_in_schema=False)
def root():
    """Redireciona a raiz para o Swagger."""
    return RedirectResponse(url="/docs")
