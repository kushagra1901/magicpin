#!/usr/bin/env python3
"""
Regenerates submission.jsonl by running bot.compose() over the 30 canonical
test pairs in dataset/test_pairs.json.

Usage:
    python generate_dataset.py --seed-dir . --out ../expanded   # (from magicpin's dataset/ dir, once)
    python generate_submission.py --dataset-dir ../expanded --out submission.jsonl
"""
from __future__ import annotations

import argparse
import json
import os

import bot


def load(base: str, kind: str, name: str) -> dict:
    with open(os.path.join(base, kind, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", default="../expanded",
                     help="Directory containing categories/, merchants/, customers/, triggers/, test_pairs.json")
    ap.add_argument("--out", default="submission.jsonl")
    args = ap.parse_args()

    pairs = json.load(open(os.path.join(args.dataset_dir, "test_pairs.json")))["pairs"]
    cat_cache: dict[str, dict] = {}

    rows = []
    for p in pairs:
        trigger = load(args.dataset_dir, "triggers", p["trigger_id"])
        merchant = load(args.dataset_dir, "merchants", p["merchant_id"])
        slug = merchant["category_slug"]
        if slug not in cat_cache:
            cat_cache[slug] = load(args.dataset_dir, "categories", slug)
        category = cat_cache[slug]
        customer = load(args.dataset_dir, "customers", p["customer_id"]) if p.get("customer_id") else None

        result = bot.compose(category, merchant, trigger, customer)
        rows.append({"test_id": p["test_id"], **result})

    with open(args.out, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
