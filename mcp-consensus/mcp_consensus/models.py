from pydantic import BaseModel, Field


DEFAULT_WORKERS = [
    "gemini-3.5-flash",
    "llama-3.3-70b",
    "mistral-small",
    "codestral",
    "nemotron-ultra",
]

DEFAULT_ARBITER = "gemini-3.5-flash"


class ConsensusRequest(BaseModel):
    prompt: str = Field(..., description="The task, question, or code to evaluate")
    worker_models: list[str] | None = Field(
        default=None,
        description="Override default worker models. If not set, uses all available models.",
    )
    arbiter_model: str | None = Field(
        default=None,
        description="Override default arbiter model.",
    )
    temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Temperature for worker responses.",
    )
    timeout_seconds: int = Field(
        default=60,
        ge=5,
        le=300,
        description="Per-worker timeout in seconds.",
    )
    dry_run: bool = Field(
        default=False,
        description="Return constructed prompts without calling any models.",
    )


class FailedWorker(BaseModel):
    model: str
    error: str


class WorkerResponse(BaseModel):
    model: str
    response: str
    latency_ms: int


class ConsensusResponse(BaseModel):
    synthesized_response: str
    arbiter_model: str
    execution_time_ms: int
    successful_workers: list[str]
    failed_workers: list[FailedWorker]
    raw_worker_responses: list[WorkerResponse]
