from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from billing.models import Payment, Refund


@pytest.mark.django_db
def test_payment_success_unique_per_intent(user):
    payment = Payment.objects.create(
        user=user,
        provider="bazaar_iap",
        intent_id="req_123",
        amount=1000,
        status=Payment.Status.SUCCESS,
    )

    with pytest.raises(ValidationError):
        Payment.objects.create(
            user=user,
            provider="bazaar_iap",
            intent_id="req_123",
            amount=1000,
            status=Payment.Status.SUCCESS,
        )

    assert payment.status == Payment.Status.SUCCESS


@pytest.mark.django_db
def test_provider_ref_unique_constraint(user):
    Payment.objects.create(
        user=user,
        provider="bazaar_iap",
        intent_id="req_a",
        amount=1000,
        provider_ref="ref-1",
    )

    with pytest.raises(ValidationError):
        Payment.objects.create(
            user=user,
            provider="bazaar_iap",
            intent_id="req_b",
            amount=1000,
            provider_ref="ref-1",
        )


@pytest.mark.django_db
def test_refund_mark_processed(user):
    payment = Payment.objects.create(
        user=user,
        provider="bazaar_iap",
        intent_id="req_z",
        amount=1000,
    )

    refund = Refund.objects.create(payment=payment, amount=500, reason="test")
    refund.mark_processed(Refund.Status.SUCCEEDED, provider_refund_id="r1", note="done")

    assert refund.status == Refund.Status.SUCCEEDED
    assert refund.provider_refund_id == "r1"
    assert refund.note == "done"
