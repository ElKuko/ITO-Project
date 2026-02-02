# ML Project

A machine learning project template.

## Project Structure

```
├── configs/          # Configuration files (hyperparameters, paths)
├── data/
│   ├── raw/          # Original, immutable data
│   └── processed/    # Cleaned and transformed data
├── models/           # Trained model artifacts
├── notebooks/        # Jupyter notebooks for exploration
├── src/              # Source code
│   ├── data.py       # Data loading and preprocessing
│   ├── train.py      # Model training
│   └── predict.py    # Inference / prediction
└── tests/            # Unit tests
```

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# Train a model
python -m src.train --config configs/default.yaml

# Run predictions
python -m src.predict --model models/model.pkl --input data/raw/input.csv
```

## Testing

```bash
pytest tests/
```
