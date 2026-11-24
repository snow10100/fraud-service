"""Data checks: the input data is what the model and the service expect.

A model can be wrong while all code "runs fine" if the data underneath it changes.
These tests fail loudly when a data file drifts from its contract.
"""
from datetime import datetime

import pandas as pd
import pytest

from fraud_service.domain.entities import Channel

TRANSACTIONS = "data/transactions_sample.csv"
GOLDEN = "data/golden_scores_v3.csv"


@pytest.fixture(scope="module")
def txns() -> pd.DataFrame:
    return pd.read_csv(TRANSACTIONS)


@pytest.fixture(scope="module")
def golden() -> pd.DataFrame:
    return pd.read_csv(GOLDEN)


@pytest.mark.data
def test_transactions_have_the_expected_columns(txns):
    assert list(txns.columns) == ["transaction_id", "amount_sar", "channel", "merchant_category",
                                  "customer_id", "timestamp", "is_fraud"]


@pytest.mark.data
def test_no_missing_values(txns, golden):
    assert not txns.isna().any().any()
    assert not golden.isna().any().any()


@pytest.mark.data
def test_transaction_ids_are_unique(txns):
    assert txns["transaction_id"].is_unique


@pytest.mark.data
def test_amounts_are_within_the_api_contract(txns):
    # The API accepts 0 < amount_sar <= 1,000,000; training data must sit inside that range.
    assert (txns["amount_sar"] > 0).all()
    assert (txns["amount_sar"] <= 1_000_000).all()


@pytest.mark.data
def test_channels_are_known_values(txns):
    assert set(txns["channel"]) <= {c.value for c in Channel}


@pytest.mark.data
def test_every_timestamp_has_a_timezone(txns):
    # Features use the UTC hour; a timestamp without a timezone would be ambiguous.
    assert all(datetime.fromisoformat(t).tzinfo is not None for t in txns["timestamp"])


@pytest.mark.data
def test_labels_are_binary_and_fraud_is_present_but_rare(txns):
    assert set(txns["is_fraud"]) <= {0, 1}
    rate = txns["is_fraud"].mean()
    assert 0.01 < rate < 0.5, f"unexpected fraud rate {rate:.1%}"


@pytest.mark.data
def test_golden_file_matches_the_transactions(txns, golden):
    # Same rows, same order, same inputs: otherwise the golden test compares the wrong things.
    assert len(golden) == len(txns)
    assert (golden["transaction_id"] == txns["transaction_id"]).all()
    assert (golden["amount_sar"] == txns["amount_sar"]).all()


@pytest.mark.data
def test_golden_scores_are_probabilities(golden):
    assert golden["score"].between(0, 1).all()
