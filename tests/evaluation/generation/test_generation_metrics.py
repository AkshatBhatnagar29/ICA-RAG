import pytest

from app.services.evaluation.metrics import unsupported_claim_rate


def test_unsupported_claims_are_measured_independently() -> None:
    assert unsupported_claim_rate([True, False, False]) == pytest.approx(2 / 3)
    assert unsupported_claim_rate([]) == 0.0
