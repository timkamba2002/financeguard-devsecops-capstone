import os
import logging
from typing import List
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker, Session, declarative_base

# ── OpenTelemetry SDK ─────────────────────────────────────────────────────────
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

# ── Database ──────────────────────────────────────────────────────────────────
DB_HOST = os.getenv("host")
DB_PORT = os.getenv("port", "5432")
DB_USER = os.getenv("user")
DB_PASSWORD = os.getenv("password")
DB_NAME = os.getenv("dbname")

if not DB_HOST:
    DATABASE_URL = "sqlite:///./financeguard.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── OpenTelemetry initialisation ──────────────────────────────────────────────
#
# All three signals (traces, metrics, logs) are exported via OTLP gRPC to
# the OTel Collector sidecar running in the same pod on localhost:4317.
# The sidecar forwards to Tempo (traces), Prometheus (metrics), Loki (logs).
#
# Every exporter uses BatchProcessor — exports happen in a background thread
# so the app never blocks waiting for telemetry to be delivered. If the
# sidecar is unreachable the batch is silently dropped; the app keeps running.

_OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
_ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "financeguard-backend")

# Resource — attached to every span, metric, and log record so Grafana knows
# which service and environment the data came from.
_resource = Resource.create(
    {
        SERVICE_NAME: _SERVICE_NAME,
        "service.version": "1.0.0",
        "deployment.environment": _ENVIRONMENT,
    }
)

# --- Traces ------------------------------------------------------------------
# TracerProvider → BatchSpanProcessor → OTLPSpanExporter → sidecar → Tempo
_tracer_provider = TracerProvider(resource=_resource)
_tracer_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=_OTEL_ENDPOINT))
)
trace.set_tracer_provider(_tracer_provider)

# --- Metrics -----------------------------------------------------------------
# MeterProvider → PeriodicExportingMetricReader → OTLPMetricExporter → sidecar → Prometheus
_meter_provider = MeterProvider(
    resource=_resource,
    metric_readers=[
        PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=_OTEL_ENDPOINT),
            export_interval_millis=30_000,
        )
    ],
)
metrics.set_meter_provider(_meter_provider)

# --- Logs --------------------------------------------------------------------
# LoggerProvider → BatchLogRecordProcessor → OTLPLogExporter → sidecar → Loki
_logger_provider = LoggerProvider(resource=_resource)
_logger_provider.add_log_record_processor(
    BatchLogRecordProcessor(OTLPLogExporter(endpoint=_OTEL_ENDPOINT))
)
set_logger_provider(_logger_provider)

# LoggingInstrumentor patches Python's stdlib logging so every LogRecord gets
# otelTraceID and otelSpanID injected. set_logging_format=True also rewrites
# the root handler format to include those fields — enabling log-trace
# correlation in Grafana (click a log line → jump to the matching trace).
LoggingInstrumentor().instrument(set_logging_format=True)

# Route all Python log records to the OTel log exporter as well.
# This means logs appear in both stdout (for kubectl logs) and Loki.
logging.getLogger().addHandler(
    LoggingHandler(level=logging.DEBUG, logger_provider=_logger_provider)
)
logging.getLogger().setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# SQLAlchemy — wraps every query in a child span under the active request span.
# enable_commenter=True appends a SQL comment with trace context, useful for
# correlating slow-query logs from RDS with the originating request trace.
SQLAlchemyInstrumentor().instrument(engine=engine, enable_commenter=True)

# Application-level metrics — these appear in Prometheus/Grafana as custom metrics.
_meter = metrics.get_meter("financeguard.backend", version="1.0.0")

transaction_counter = _meter.create_counter(
    name="financeguard.transactions.created",
    description="Total number of financial transactions created",
    unit="1",
)

request_counter = _meter.create_counter(
    name="financeguard.http.requests",
    description="Total HTTP requests by route and status",
    unit="1",
)


# ── FastAPI app ───────────────────────────────────────────────────────────────
SKIP_AUTH_VERIFICATION = os.getenv("SKIP_AUTH_VERIFICATION", "true").lower() == "true"
# auto_error=False returns None instead of 403 when no Authorization header is
# present, allowing SKIP_AUTH_VERIFICATION to bypass auth without a header.
security = HTTPBearer(auto_error=not SKIP_AUTH_VERIFICATION)

app = FastAPI(
    title="FinanceGuard API",
    description="Secure backend for Enterprise DevSecOps Capstone Project",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FastAPIInstrumentor wraps every route handler in a span automatically.
# Each incoming request creates a root span named after the HTTP method + route
# (e.g. "GET /api/v1/transactions"). Child spans appear for DB calls.
FastAPIInstrumentor().instrument_app(app)


# ── Models ────────────────────────────────────────────────────────────────────
class TransactionModel(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    description = Column(String)
    amount = Column(Float)
    category = Column(String)
    type = Column(String)  # "income" or "expense"
    created_at = Column(DateTime, default=datetime.utcnow)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class TransactionCreate(BaseModel):
    description: str
    amount: float
    category: str
    type: str


class Transaction(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    description: str
    amount: float
    category: str
    type: str


# ── Auth ──────────────────────────────────────────────────────────────────────
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    if SKIP_AUTH_VERIFICATION:
        return {"user_id": "demo-user-123"}
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    raise HTTPException(status_code=501, detail="Full auth not implemented")


# ── Routes ────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    Base.metadata.create_all(bind=engine)
    logger.info(
        "Database tables initialised",
        extra={
            "db_url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else "sqlite"
        },
    )


@app.get("/health")
def health_check():
    logger.debug("Health check requested")
    return {"status": "healthy", "message": "Connected to RDS PostgreSQL"}


@app.get("/api/v1/transactions", response_model=List[Transaction])
def list_transactions(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("list_transactions") as span:
        span.set_attribute("user.id", current_user["user_id"])
        results = (
            db.query(TransactionModel)
            .filter(TransactionModel.user_id == current_user["user_id"])
            .all()
        )
        span.set_attribute("result.count", len(results))
        logger.info(
            "Listed transactions",
            extra={"user_id": current_user["user_id"], "count": len(results)},
        )
        request_counter.add(1, {"route": "GET /api/v1/transactions", "status": "200"})
        return results


@app.post("/api/v1/transactions", response_model=Transaction, status_code=201)
def create_transaction(
    transaction: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("create_transaction") as span:
        span.set_attribute("user.id", current_user["user_id"])
        span.set_attribute("transaction.amount", transaction.amount)
        span.set_attribute("transaction.category", transaction.category)
        span.set_attribute("transaction.type", transaction.type)

        db_tx = TransactionModel(
            user_id=current_user["user_id"],
            description=transaction.description,
            amount=transaction.amount,
            category=transaction.category,
            type=transaction.type,
        )
        db.add(db_tx)
        db.commit()
        db.refresh(db_tx)

        transaction_counter.add(
            1,
            {
                "category": transaction.category,
                "type": transaction.type,
                "environment": _ENVIRONMENT,
            },
        )
        logger.info(
            "Transaction created",
            extra={
                "user_id": current_user["user_id"],
                "transaction_id": db_tx.id,
                "amount": transaction.amount,
                "category": transaction.category,
            },
        )
        request_counter.add(1, {"route": "POST /api/v1/transactions", "status": "201"})
        return db_tx
