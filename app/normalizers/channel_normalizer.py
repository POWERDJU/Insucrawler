from __future__ import annotations

import csv
from pathlib import Path


class ChannelNormalizer:
    def __init__(self, dictionary_path: str | Path = "config/channel_dictionary.csv") -> None:
        self.dictionary_path = Path(dictionary_path)
        self.mapping: dict[str, str] = {}
        self.load()

    def load(self) -> None:
        if not self.dictionary_path.exists():
            return
        with self.dictionary_path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                self.mapping[row["keyword"]] = row["normalized_channel"]

    def normalize_many(self, channels: list[str] | None) -> list[str]:
        result: list[str] = []
        for channel in channels or []:
            normalized = self.mapping.get(channel, channel)
            if normalized not in result:
                result.append(normalized)
        return result
