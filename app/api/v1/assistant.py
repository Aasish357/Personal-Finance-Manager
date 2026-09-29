from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.v1.analytics import get_budget_vs_actual, get_overview
from app.core.config import settings
from app.core.deps import get_current_user
from app.db.database import get_db
from app.db.models.user import User
from app.schemas.assistant import ChatRequest, ChatResponse
from app.utils import ollama
from app.utils.ollama import OllamaError

router = APIRouter()

SYSTEM_PROMPT = (
    "You are a personal finance assistant embedded in a budgeting app. "
    "Answer questions about the user's spending, budgets, and alerts using "
    "only the financial summary provided below. Be concise and concrete "
    "(use real numbers from the summary). If the summary doesn't contain "
    "what's needed to answer, say so plainly instead of guessing.\n"
    "Reading the summary: every budget line ends with its status in plain words. "
    "Only a line marked 'OVER BUDGET' is over; a line marked 'within budget' "
    "is not, however high its utilization percentage looks. Copy the amounts "
    "from the status text rather than recomputing them, and never quote a "
    "utilization percentage as if it were a currency amount."
)


def _build_financial_summary(overview: dict, budget_rows: list[dict]) -> str:
    lines = [
        f"Balance: {overview['balance']}",
        f"All-time income: {overview['total_income']}, all-time expenses: {overview['total_expense']}",
        f"This month — income: {overview['current_month_income']}, expenses: {overview['current_month_expense']}",
        f"Active alerts: {overview['active_alerts']}",
    ]
    if budget_rows:
        lines.append("Budgets:")
        for row in budget_rows[:10]:
            # State the status in words, and give the remaining/overage amount
            # outright, so the model never has to subtract -- small local models
            # otherwise misread a utilization percentage as a currency overage.
            remaining = round(row["budgeted"] - row["spent"], 2)
            status = (
                f"OVER BUDGET by {abs(remaining)}"
                if remaining < 0
                else f"within budget, {remaining} remaining"
            )
            lines.append(
                f"  - {row['category_name']} ({row['month']}): "
                f"budget {row['budgeted']} | spent {row['spent']} | "
                f"utilization {row['utilization_pct']}% | {status}"
            )
    else:
        lines.append("Budgets: none set yet.")
    return "\n".join(lines)


def _fallback_reply(message: str, overview: dict, budget_rows: list[dict]) -> str:
    """
    Rule-based reply used when the local Ollama model is unreachable, so the
    assistant page still answers real questions about your data out of the box.
    """
    lowered = message.lower()

    if "balance" in lowered:
        return f"Your current balance is {overview['balance']:.2f} (income {overview['total_income']:.2f} minus expenses {overview['total_expense']:.2f})."

    if "budget" in lowered or "over" in lowered:
        over_budget = [r for r in budget_rows if r["utilization_pct"] >= 100]
        if over_budget:
            names = ", ".join(f"{r['category_name']} ({r['utilization_pct']}%)" for r in over_budget)
            return f"You're over budget in: {names}."
        if budget_rows:
            return "You're within budget in every category you've set a budget for. Nice."
        return "You haven't set any budgets yet — add one from the Budgets page to start tracking this."

    if "alert" in lowered:
        count = overview["active_alerts"]
        return f"You have {count} active alert{'s' if count != 1 else ''}." if count else "No active alerts right now."

    if "month" in lowered or "spend" in lowered or "spent" in lowered:
        return (
            f"This month you've earned {overview['current_month_income']:.2f} and spent "
            f"{overview['current_month_expense']:.2f}."
        )

    return (
        "I can answer questions about your balance, this month's spending, and your budgets. "
        "Try asking something like \"am I over budget anywhere?\" or \"what's my balance?\""
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    overview = await get_overview(db=db, current_user=current_user)
    budget_rows = await get_budget_vs_actual(db=db, current_user=current_user)

    try:
        summary = _build_financial_summary(overview, budget_rows)
        reply = await run_in_threadpool(
            ollama.chat,
            f"{SYSTEM_PROMPT}\n\n{summary}",
            [{"role": h.role, "content": h.content} for h in request.history[-10:]],
            request.message,
        )
    except OllamaError as exc:
        # Ollama down, model not pulled, or an empty reply. Answer from the
        # rule-based path rather than failing the request.
        reply = f"{_fallback_reply(request.message, overview, budget_rows)}  ({exc})"

    return ChatResponse(reply=reply, generated_at=datetime.now(timezone.utc))


@router.get("/status")
async def assistant_status(current_user: User = Depends(get_current_user)):
    """
    Lets the UI show which model is in use and whether Ollama is reachable,
    so "the assistant answered oddly" is easy to trace to a config problem.
    """
    available = await run_in_threadpool(ollama.is_available)
    models: list[str] = []
    if available:
        try:
            models = await run_in_threadpool(ollama.list_models)
        except OllamaError:
            models = []

    return {
        "provider": "ollama",
        "base_url": settings.ollama_base_url,
        "model": settings.ollama_model,
        "available": available,
        "model_installed": settings.ollama_model in models,
        "available_models": models,
    }
