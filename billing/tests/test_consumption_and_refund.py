from __future__ import annotations

import pytest

from billing import services
from billing.exceptions import RefundNotAllowed
from billing.models import Payment


@pytest.mark.django_db
def test_mark_consumed_sets_timestamp(user):
    payment = Payment.objects.create(
        user=user,
        provider="bazaar_iap",
        intent_id="req_1",
        amount=1000,
        status=Payment.Status.SUCCESS,
    )

    services.mark_consumed(payment)
    payment.refresh_from_db()
    assert payment.consumed_at is not None


@pytest.mark.django_db
def test_refund_full_success(monkeypatch, user):
    class DummyProvider:
        def refund(self, payment, amount: int, reason: str = ""):
            return {"status": "succeeded", "provider_ref": "refund-1"}

    monkeypatch.setattr(services, "_get_provider", lambda code: DummyProvider())

    payment = Payment.objects.create(
        user=user,
        provider="bazaar_iap",
        intent_id="req_2",
        amount=2000,
        status=Payment.Status.SUCCESS,
    )

    refund = services.refund_full(payment, reason="cancel")
    assert refund.status == refund.Status.SUCCEEDED


@pytest.mark.django_db
def test_refund_partial_requires_consumed(monkeypatch, user):
    class DummyProvider:
        def refund(self, payment, amount: int, reason: str = ""):
            return {"status": "succeeded", "provider_ref": "refund-2"}

    monkeypatch.setattr(services, "_get_provider", lambda code: DummyProvider())

    payment = Payment.objects.create(
        user=user,
        provider="bazaar_iap",
        intent_id="req_3",
        amount=3000,
        status=Payment.Status.SUCCESS,
    )

    services.mark_consumed(payment)

    refund = services.refund_partial(payment, amount=500, reason="partial")
    assert refund.amount == 500


@pytest.mark.django_db
def test_refund_partial_not_allowed_when_not_consumed(monkeypatch, user):
    monkeypatch.setattr(services, "_get_provider", lambda code: object())

    payment = Payment.objects.create(
        user=user,
        provider="bazaar_iap",
        intent_id="req_4",
        amount=3000,
        status=Payment.Status.SUCCESS,
    )

    with pytest.raises(RefundNotAllowed):
        services.refund_partial(payment, amount=500, reason="partial")
