"""The stricter wire contract (extension): no silent coercion of amounts or timestamps."""
import pytest
from pydantic import ValidationError

from fraud_service.api.schemas import PredictRequest

VALID = {
    "transaction_id": "TXN-2026-00042", "amount_sar": 249.99, "channel": "ecom",
    "merchant_category": "electronics", "customer_id": "CUST-00077",
    "timestamp": "2026-07-05T03:30:00+00:00",
}


@pytest.mark.unit
@pytest.mark.parametrize("field, value", [
    ("amount_sar", "249.99"),               # numeric string: was coerced to 249.99 before
    ("amount_sar", True),                   # boolean: was coerced to 1.0 before
    ("timestamp", "2026-07-05T03:30:00"),   # no timezone: was accepted as naive before
    ("timestamp", "2026-07-05"),            # date only, no time and no timezone
])
def test_ambiguous_input_is_rejected(field, value):
    with pytest.raises(ValidationError):
        PredictRequest.model_validate({**VALID, field: value})


@pytest.mark.unit
@pytest.mark.parametrize("field, value", [
    ("amount_sar", 250),                            # an integer JSON number is still a number
    ("timestamp", "2026-07-05T06:30:00+03:00"),     # any explicit offset is fine
])
def test_unambiguous_input_is_still_accepted(field, value):
    req = PredictRequest.model_validate({**VALID, field: value})
    assert req.to_domain().timestamp.utcoffset() is not None


@pytest.mark.unit
def test_riyadh_offset_maps_to_the_same_utc_hour():
    """06:30 in Riyadh is 03:30 UTC: the feature must not depend on how the client wrote it."""
    utc = PredictRequest.model_validate(VALID).to_domain().to_features()
    riyadh = PredictRequest.model_validate(
        {**VALID, "timestamp": "2026-07-05T06:30:00+03:00"}).to_domain().to_features()
    assert utc.values["is_night"] == riyadh.values["is_night"] == 1


@pytest.mark.unit
def test_naive_domain_timestamp_is_read_as_utc(make_txn, sample_txn):
    """Batch CSV rows reach the domain directly; a naive time there means UTC."""
    naive = make_txn(timestamp=sample_txn.timestamp.replace(tzinfo=None))
    assert naive.to_features().values == sample_txn.to_features().values
