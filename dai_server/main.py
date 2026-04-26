"""
DAI Server — FastAPI Application
==================================

Starts the DAI decision ledger server.

    uvicorn dai_server.main:app --reload
"""

import json
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC
from typing import Any

# load_dotenv() MUST be called before any module that reads os.environ at import
# time (e.g. SQLAlchemy engine creation). The E402 noqa below is intentional.
from dotenv import load_dotenv  # noqa: E402

load_dotenv()  # noqa: E402

from fastapi import Depends, FastAPI, Request, Response  # noqa: E402
from fastapi import Query as FQuery  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse, PlainTextResponse  # noqa: E402
from prometheus_fastapi_instrumentator import Instrumentator  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from dai.hash_chain import verify_chain  # noqa: E402
from dai.models import Article19ExportRequest, DecisionRecord  # noqa: E402
from dai_server.db.models import DecisionORM  # noqa: E402
from dai_server.db.session import close_engine, create_tables, get_db  # noqa: E402
from dai_server.export.article19 import generate_article19_export  # noqa: E402
from dai_server.export.article19_pdf import generate_article19_pdf  # noqa: E402
from dai_server.routes import ingest, policy, query, verify  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Startup and shutdown lifecycle."""
    await create_tables()
    yield
    await close_engine()


app = FastAPI(
    title="DAI — Decision Authority Infrastructure",
    version="0.1.0",
    description=(
        "Append-only decision ledger for AI agents in regulated environments. "
        "EU AI Act Article 19 compliant by design."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS Middleware ────────────────────────────────────────────────────────────

cors_origins_env = os.environ.get("DAI_CORS_ORIGINS", "")
cors_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request Timing Middleware ──────────────────────────────────────────────────


@app.middleware("http")
async def add_process_time_header(request: Request, call_next: Any) -> Response:
    t0 = time.monotonic()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{(time.monotonic() - t0) * 1000:.2f}ms"
    return response


# ── Prometheus Metrics ─────────────────────────────────────────────────────────

instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_instrument_requests_inprogress=True,
    excluded_handlers=[".*admin.*", "/metrics", "/health"],
    inprogress_name="dai_inprogress",
    inprogress_labels=True,
)
instrumentator.instrument(app).expose(app)

# ── API Key Authentication Middleware ─────────────────────────────────────────

_UNPROTECTED_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}


@app.middleware("http")
async def api_key_middleware(request: Request, call_next: Any) -> Response:
    if request.url.path in _UNPROTECTED_PATHS:
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing API key. Use: Authorization: Bearer <key>"},
        )

    token = auth_header[7:]

    # Fallback to the environment bootstrap key
    env_key = os.environ.get("DAI_API_KEY")
    if env_key and token == env_key:
        request.state.agent_id = "bootstrap_admin"
        request.state.roles = "admin,read,write"
        return await call_next(request)

    # Database API Key lookup
    import hashlib

    from sqlalchemy import select

    from dai_server.db.models import ApiKeyORM
    from dai_server.db.session import get_session_factory

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(ApiKeyORM).where(ApiKeyORM.key_hash == token_hash))
        api_key = result.scalar_one_or_none()

    if not api_key:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid API key."},
        )

    request.state.agent_id = api_key.agent_id
    request.state.roles = api_key.roles

    return await call_next(request)


# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(ingest.router)
app.include_router(query.router)
app.include_router(verify.router)
app.include_router(policy.router)


@app.get("/health", tags=["Health"])
async def health() -> dict:
    """Health check endpoint. No authentication required."""
    return {"status": "ok", "version": "0.1.0"}


# ── Article 19 Export Route ───────────────────────────────────────────────────


@app.post(
    "/export/article19",
    tags=["Export"],
    responses={
        200: {
            "description": "Compliance export (format via ?format= query param)",
            "content": {
                "application/json": {},
                "application/pdf": {},
                "text/plain": {},
            },
        }
    },
)
async def export_article19(
    request: Article19ExportRequest,
    format: str = FQuery(  # noqa: A002
        default="json",
        description="Output format: json | pdf | text",
    ),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Generate an EU AI Act Article 19 compliance export.

    **Format options (via `?format=` query param):**
    - `json`  — Machine-readable JSON *(default)*
    - `pdf`   — Professional branded PDF report (A4)
    - `text`  — Human-readable plain text
    """
    from sqlalchemy import select

    stmt = (
        select(DecisionORM)
        .where(
            DecisionORM.decision_timestamp >= request.from_timestamp,
            DecisionORM.decision_timestamp <= request.to_timestamp,
        )
        .order_by(DecisionORM.decision_timestamp)
    )
    if request.agent_ids:
        stmt = stmt.where(DecisionORM.agent_id.in_(request.agent_ids))
    if request.decision_types:
        stmt = stmt.where(DecisionORM.decision_type.in_(request.decision_types))

    result = await db.execute(stmt)
    rows = result.scalars().all()
    records = [DecisionRecord(**json.loads(r.full_record_json)) for r in rows]

    if request.include_chain_proof:
        chain_result = verify_chain(records)
    else:
        from dai.models import ChainVerifyResult

        chain_result = ChainVerifyResult(
            valid=True,
            total_records=len(records),
            verified_at=__import__("datetime").datetime.now(UTC),
            message="Chain proof not requested.",
        )

    export = generate_article19_export(
        records, request.from_timestamp, request.to_timestamp, chain_result
    )

    if format == "pdf":
        pdf_bytes = generate_article19_pdf(export)
        ts = export.generated_at.strftime("%Y%m%d_%H%M%S")
        filename = f"article19_report_{ts}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    if format == "text":
        return PlainTextResponse(content=export.to_text_report())
    return JSONResponse(content=json.loads(export.to_json()))


# Required for middleware type hints
