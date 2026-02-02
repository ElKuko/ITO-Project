"""Model training script."""

import argparse
import logging
from pathlib import Path

import joblib
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

from src.data import load_data, preprocess, split_data

logger = logging.getLogger(__name__)


def build_model(config: dict):
    """Instantiate a model from config."""
    return RandomForestClassifier(
        n_estimators=config.get("n_estimators", 100),
        max_depth=config.get("max_depth", None),
        random_state=config.get("random_state", 42),
    )


def train(config: dict):
    """Full training pipeline: load data, train model, evaluate, and save."""
    df = load_data(config["data_path"])
    X, y = preprocess(df, target_column=config["target_column"])
    X_train, X_test, y_train, y_test = split_data(
        X, y, test_size=config.get("test_size", 0.2)
    )

    logger.info("Training set: %d samples, Test set: %d samples", len(X_train), len(X_test))

    model = build_model(config.get("model", {}))
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    logger.info("Test accuracy: %.4f", acc)
    logger.info("\n%s", classification_report(y_test, y_pred))

    model_path = Path(config.get("model_path", "models/model.pkl"))
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    logger.info("Model saved to %s", model_path)

    return model, acc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train a model")
    parser.add_argument("--config", required=True, help="Path to YAML config file")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    with open(args.config) as f:
        config = yaml.safe_load(f)

    train(config)
