# config.py
import yaml
from dataclasses import dataclass

@dataclass
class DataConfig:
    size: int = 100
    synthetic: bool = True

@dataclass
class TimingConfig:
    distribution: str = "poisson"
    rate: float = 1.0

@dataclass
class WorkerConfig:
    endpoint: str = "http://localhost:8000/process"
    concurrency: int = 5

@dataclass
class RecordsConfig:
    output_file: str = "records.json"

@dataclass
class Config:
    dataset: DataConfig
    timing: TimingConfig
    worker: WorkerConfig
    records: RecordsConfig


def load_config(path: str) -> Config:
    with open(path) as f:
        data = yaml.safe_load(f)
    dataset = DataConfig(**data.get("dataset", {}))
    timing = TimingConfig(**data.get("timing", {}))
    worker = WorkerConfig(**data.get("worker", {}))
    records = RecordsConfig(**data.get("records", {}))
    return Config(dataset=dataset, timing=timing, worker=worker, records=records) 