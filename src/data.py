"""Data loading and preprocessing utilities."""

import argparse
import logging
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)


def load_data(path: str) -> pd.DataFrame:
    """Load a dataset from a CSV file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    logger.info("Loading data from %s", path)
    return pd.read_csv(path)


def preprocess(df: pd.DataFrame, target_column: str) -> tuple:
    """Split a DataFrame into features and target."""
    if target_column not in df.columns:
        raise ValueError(f"Target column '{target_column}' not found in data")
    X = df.drop(columns=[target_column])
    y = df[target_column]
    return X, y


def split_data(X, y, test_size: float = 0.2, random_state: int = 42):
    """Split data into train and test sets."""
    return train_test_split(X, y, test_size=test_size, random_state=random_state)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preprocess raw data")
    parser.add_argument("--input", required=True, help="Path to raw CSV data")
    parser.add_argument("--output", required=True, help="Path to save processed data")
    parser.add_argument("--target", required=True, help="Name of target column")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    df = load_data(args.input)
    logger.info("Loaded %d rows, %d columns", *df.shape)
    df.to_csv(args.output, index=False)
    logger.info("Saved processed data to %s", args.output)
