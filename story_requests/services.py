from __future__ import annotations

from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import QuerySet

from .models import RequestTransition, StoryRequest, TransitionRule
from .signals import story_ready

MAX_OPEN_REQUESTS = 2
MAX_FREE_REQUESTS_PER_DAY = 3

TRANSITION_RULES: tuple[TransitionRule, ...] = (
    TransitionRule(StoryRequest.Status.SUBMITTED, StoryRequest.Status.PAYMENT_REQUIRED),
    TransitionRule(StoryRequest.Status.SUBMITTED, StoryRequest.Status.QUEUED_FREE),
    TransitionRule(StoryRequest.Status.PAYMENT_REQUIRED, StoryRequest.Status.QUEUED_PAID),
    TransitionRule(StoryRequest.Status.QUEUED_FREE, StoryRequest.Status.IN_PROGRESS),
    TransitionRule(StoryRequest.Status.QUEUED_PAID, StoryRequest.Status.IN_PROGRESS),
    TransitionRule(StoryRequest.Status.IN_PROGRESS, StoryRequest.Status.REVIEW_PENDING),
    TransitionRule(StoryRequest.Status.REVIEW_PENDING, StoryRequest.Status.READY_FOR_USER),
)

TRANSITION_MAP: dict[str, set[str]] = defaultdict(set)
for rule in TRANSITION_RULES:
    TRANSITION_MAP[rule.source].add(rule.destination)


def _ensure_transition_allowed(current: str, target: str) -> None:
    if current == StoryRequest.Status.CANCELED:
        raise ValidationError("درخواست لغو شده است.")

    if target == StoryRequest.Status.CANCELED:
        return

    if target not in TRANSITION_MAP.get(current, set()):
        raise ValidationError("تغییر وضعیت در این مرحله مجاز نیست.")


def enqueue_request(request: StoryRequest, *, actor=None, note: str | None = None) -> StoryRequest:
    """Handle initial state transitions after creation based on plan."""
    if request.plan == StoryRequest.Plan.PAID:
        return transition(
            request,
            StoryRequest.Status.PAYMENT_REQUIRED,
            actor=actor,
            note=note or "در انتظار پرداخت",
        )
    return transition(
        request,
        StoryRequest.Status.QUEUED_FREE,
        actor=actor,
        note=note or "ورود به صف رایگان",
    )


def calc_position(request: StoryRequest) -> int:
    """Return the 0-based index of the request inside its queue."""
    if request.status not in StoryRequest.QUEUED_STATUSES:
        return 0

    queue_status = (
        StoryRequest.Status.QUEUED_PAID
        if request.plan == StoryRequest.Plan.PAID
        else StoryRequest.Status.QUEUED_FREE
    )
    qs: QuerySet[StoryRequest] = (
        StoryRequest.objects.filter(
            status=queue_status,
            plan=request.plan,
            created_at__lt=request.created_at,
        )
        .order_by("created_at")
        .only("id")
    )
    return qs.count()


def transition(
    story_request: StoryRequest,
    to_status: str,
    *,
    actor=None,
    note: str = "",
) -> StoryRequest:
    """Move a story request to the desired status, logging the change."""
    with transaction.atomic():
        locked = (
            StoryRequest.objects.select_for_update()
            .select_related("user")
            .get(pk=story_request.pk)
        )

        current_status = locked.status
        if current_status == to_status:
            return locked

        _ensure_transition_allowed(current_status, to_status)

        locked.status = to_status
        fields_to_update: list[str] = ["status", "updated_at"]

        if to_status == StoryRequest.Status.QUEUED_PAID:
            if locked.queue_priority != StoryRequest.PRIORITY_PAID:
                locked.queue_priority = StoryRequest.PRIORITY_PAID
                fields_to_update.append("queue_priority")
        elif to_status == StoryRequest.Status.QUEUED_FREE:
            if locked.queue_priority != StoryRequest.PRIORITY_FREE:
                locked.queue_priority = StoryRequest.PRIORITY_FREE
                fields_to_update.append("queue_priority")

        if to_status in StoryRequest.QUEUED_STATUSES:
            position = calc_position(locked)
            if locked.position_hint != position:
                locked.position_hint = position
                fields_to_update.append("position_hint")
        else:
            if locked.position_hint != 0:
                locked.position_hint = 0
                fields_to_update.append("position_hint")

        locked.save(update_fields=fields_to_update)

        if to_status == StoryRequest.Status.IN_PROGRESS and locked.payment_id:
            try:
                from billing import services as billing_services

                billing_services.mark_consumed(locked.payment)
            except Exception:  # pragma: no cover - avoid breaking transition on billing failure
                pass

        RequestTransition.objects.create(
            request=locked,
            from_status=current_status,
            to_status=to_status,
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            note=note,
        )

        if to_status == StoryRequest.Status.READY_FOR_USER:
            transaction.on_commit(
                lambda: story_ready.send(sender=StoryRequest, request=locked)  # pragma: no cover
            )

        story_request.refresh_from_db()
        return locked


def get_request_by_intent(intent_id: str) -> StoryRequest:
    qs = StoryRequest.objects.select_related("payment")
    if intent_id.startswith("req_"):
        token = intent_id.split("_", 1)[1]
        matches = list(qs.filter(uuid__istartswith=token))
        if len(matches) == 1:
            return matches[0]
    else:
        try:
            return qs.get(uuid=intent_id)
        except StoryRequest.DoesNotExist as exc:
            raise ValidationError("درخواست داستانی با این شناسه پیدا نشد.") from exc
    raise ValidationError("درخواست داستانی با این شناسه پیدا نشد.")


def mark_paid(intent_id: str, payment=None, note: str = "پرداخت با موفقیت انجام شد.") -> StoryRequest:
    story_request = get_request_by_intent(intent_id)

    if payment and story_request.payment_id != getattr(payment, "id", None):
        story_request.payment = payment
        story_request.save(update_fields=["payment", "updated_at"])

    return transition(
        story_request,
        StoryRequest.Status.QUEUED_PAID,
        actor=None,
        note=note,
    )
