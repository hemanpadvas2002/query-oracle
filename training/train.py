"""
Fine-tune DistilBERT as a query classifier.

When you have your labelled dataset (500–2000 examples), run:
    python training/train.py --data training/data/queries.csv

The trained model is saved to training/query-classifier-final/ and can be
loaded with:
    from llm_router import DistilBERTClassifier
    clf = DistilBERTClassifier("training/query-classifier-final")

Dataset format (CSV):
    query,label
    "How many calories in a banana?",fast
    "Explain the difference between TCP and UDP.",balanced
    "Design the architecture for an AI OS.",deep

Requires:
    pip install transformers datasets torch scikit-learn optimum onnxruntime
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def train(data_path: str, output_dir: str = "training/query-classifier-final",
          epochs: int = 5, batch_size: int = 16, export_onnx: bool = True):

    try:
        import pandas as pd
        from datasets import Dataset
        from transformers import (
            DistilBertTokenizerFast,
            DistilBertForSequenceClassification,
            TrainingArguments,
            Trainer,
        )
        import torch
        import numpy as np
        from sklearn.metrics import accuracy_score, classification_report
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Run: pip install transformers datasets torch scikit-learn")
        return

    LABEL2ID = {"fast": 0, "balanced": 1, "deep": 2}
    ID2LABEL = {0: "fast", 1: "balanced", 2: "deep"}

    print(f"Loading dataset from {data_path}...")
    df = pd.read_csv(data_path)
    assert set(df["label"].unique()).issubset(LABEL2ID), \
        "Labels must be: fast, balanced, deep"

    df["label"] = df["label"].map(LABEL2ID)
    print(f"  {len(df)} examples | class distribution:\n{df['label'].value_counts().to_string()}")

    dataset = Dataset.from_pandas(df[["query", "label"]])
    dataset = dataset.train_test_split(test_size=0.15, seed=42)

    tokenizer = DistilBertTokenizerFast.from_pretrained("distilbert-base-uncased")

    def tokenize(batch):
        return tokenizer(
            batch["query"], truncation=True,
            padding="max_length", max_length=128,
        )

    dataset = dataset.map(tokenize, batched=True)
    dataset = dataset.rename_column("label", "labels")
    dataset.set_format("torch", columns=["input_ids", "attention_mask", "labels"])

    model = DistilBertForSequenceClassification.from_pretrained(
        "distilbert-base-uncased",
        num_labels=3, id2label=ID2LABEL, label2id=LABEL2ID,
    )

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        preds = np.argmax(logits, axis=-1)
        return {"accuracy": accuracy_score(labels, preds)}

    args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="accuracy",
        logging_dir="./logs/training",
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["test"],
        compute_metrics=compute_metrics,
    )

    print("\nTraining...")
    trainer.train()
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    print("\nEvaluation on test set:")
    preds_out = trainer.predict(dataset["test"])
    preds     = np.argmax(preds_out.predictions, axis=-1)
    labels    = preds_out.label_ids
    print(classification_report(labels, preds, target_names=list(LABEL2ID.keys())))

    if export_onnx:
        _export_onnx(output_dir)

    print(f"\nModel saved to {output_dir}/")
    print("Load it with:")
    print(f'    clf = DistilBERTClassifier("{output_dir}")')
    print(f'    clf_onnx = DistilBERTClassifier("{output_dir}", use_onnx=True)')


def _export_onnx(model_dir: str):
    try:
        from optimum.onnxruntime import ORTModelForSequenceClassification
        print("\nExporting to ONNX (smaller, faster, no PyTorch needed)...")
        ort_model = ORTModelForSequenceClassification.from_pretrained(
            model_dir, export=True
        )
        ort_model.save_pretrained(model_dir)
        print(f"ONNX model saved to {model_dir}/model.onnx")
    except ImportError:
        print("Skipping ONNX export (pip install optimum onnxruntime)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fine-tune DistilBERT query classifier")
    parser.add_argument("--data",       default="training/data/queries.csv")
    parser.add_argument("--output",     default="training/query-classifier-final")
    parser.add_argument("--epochs",     type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--no-onnx",    action="store_true")
    args = parser.parse_args()

    train(
        data_path=args.data,
        output_dir=args.output,
        epochs=args.epochs,
        batch_size=args.batch_size,
        export_onnx=not args.no_onnx,
    )
