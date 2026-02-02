"""Prediction / inference script."""

import argparse
import logging

import joblib
import pandas as pd

logger = logging.getLogger(__name__)


def load_model(path: str):
    """Load a trained model from disk."""
    logger.info("Loading model from %s", path)
    return joblib.load(path)


def predict(model, X: pd.DataFrame):
    """Run predictions on input features."""
    return model.predict(X)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run predictions")
    parser.add_argument("--model", required=True, help="Path to trained model")
    parser.add_argument("--input", required=True, help="Path to input CSV")
    parser.add_argument("--output", default=None, help="Path to save predictions CSV")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    model = load_model(args.model)
    df = pd.read_csv(args.input)
    preds = predict(model, df)

    results = df.copy()
    results["prediction"] = preds

    if args.output:
        results.to_csv(args.output, index=False)
        logger.info("Predictions saved to %s", args.output)
    else:
        print(results.to_string(index=False))
