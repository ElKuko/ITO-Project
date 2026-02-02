"""Tests for data loading and preprocessing."""

import pandas as pd
import pytest

from src.data import preprocess, split_data


@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "feature_1": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "feature_2": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        "target": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
    })


def test_preprocess(sample_df):
    X, y = preprocess(sample_df, target_column="target")
    assert "target" not in X.columns
    assert len(y) == 10


def test_preprocess_missing_column(sample_df):
    with pytest.raises(ValueError):
        preprocess(sample_df, target_column="nonexistent")


def test_split_data(sample_df):
    X, y = preprocess(sample_df, target_column="target")
    X_train, X_test, y_train, y_test = split_data(X, y, test_size=0.2)
    assert len(X_train) == 8
    assert len(X_test) == 2
