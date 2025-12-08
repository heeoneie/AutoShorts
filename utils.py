# utils.py
"""Utility functions for file I/O and data operations"""

import os
import json
from typing import Any, List


def ensure_output_dir(directory: str = "output") -> None:
    """
    Ensure output directory exists, create if it doesn't.

    Args:
        directory: Directory path to create
    """
    os.makedirs(directory, exist_ok=True)


def save_json(data: Any, filepath: str) -> None:
    """
    Save data to JSON file with proper encoding.

    Args:
        data: Data to serialize to JSON
        filepath: Output file path
    """
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 저장 완료: {filepath}")


def extract_keywords(top10_data: List[Dict[str, Any]], count: int = 10) -> List[str]:
    """
    Extract keyword list from top10 API data.

    Args:
        top10_data: List of trending keyword dictionaries
        count: Number of keywords to extract

    Returns:
        List of keyword strings
    """
    return [item["keyword"] for item in top10_data][:count]
