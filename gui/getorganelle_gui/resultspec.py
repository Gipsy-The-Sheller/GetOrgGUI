"""YR-MPE-compatible result objects.

The schema name and field names follow YR-MPE's ``yrmpe.result.v1`` so a
GetOrganelle result can be handed to the YR-MPE workspace unchanged.  When
this package runs inside YR-MPE, the host classes are used directly; the
standalone copy below only exists so the GUI and CLI work without the host.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

RESULT_SCHEMA = "yrmpe.result.v1"
ITEM_TYPE_SEQUENCE = "sequence"
ITEM_TYPE_TABLE = "table"
ALL_ITEM_TYPES = {
    "sequence",
    "alignment",
    "model",
    "distance",
    "phylogeny",
    "variant",
    "coalescent",
    "clock",
    "chain",
    "treeset",
    "table",
}

HOST_RESULT_CLASSES: Optional[tuple] = None
try:  # pragma: no cover - exercised only inside YR-MPE
    from YR_MPE.runtime.results import (  # type: ignore
        DatasetItemSpec as _HostDatasetItemSpec,
        DatasetSpec as _HostDatasetSpec,
        ResultSpec as _HostResultSpec,
        RunSpec as _HostRunSpec,
    )

    HOST_RESULT_CLASSES = (
        _HostDatasetItemSpec,
        _HostDatasetSpec,
        _HostRunSpec,
        _HostResultSpec,
    )
    DatasetItemSpec = _HostDatasetItemSpec
    DatasetSpec = _HostDatasetSpec
    RunSpec = _HostRunSpec
    ResultSpec = _HostResultSpec
except Exception:  # ImportError or a partially installed host

    def _jsonable(value: Any) -> Any:
        import dataclasses

        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            return _jsonable(dataclasses.asdict(value))
        if isinstance(value, dict):
            return {str(key): _jsonable(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [_jsonable(item) for item in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    @dataclass
    class DatasetItemSpec:
        loci_name: str
        item_type: str = ITEM_TYPE_SEQUENCE
        sequences: List[Any] = field(default_factory=list)
        file_path: str = ""
        format: str = "fasta"
        is_aligned: bool = False
        length: int = 0
        sequence_count: int = 0
        data: Dict[str, Any] = field(default_factory=dict)
        metadata: Dict[str, Any] = field(default_factory=dict)
        parent_index: Optional[int] = None
        selected: bool = False
        import_id: Optional[str] = None
        run_id: Optional[str] = None

        def validate(self) -> List[str]:
            problems = []
            if not self.loci_name:
                problems.append("item has no loci_name")
            if self.item_type not in ALL_ITEM_TYPES:
                problems.append("unknown item_type %r" % self.item_type)
            if not self.sequences and not self.file_path:
                problems.append("%s has neither sequences nor file_path" % self.loci_name)
            return problems

        def to_settings_dict(self) -> Dict[str, Any]:
            return _jsonable(
                {
                    "loci_name": self.loci_name,
                    "item_type": self.item_type,
                    "file_path": self.file_path,
                    "format": self.format,
                    "is_aligned": self.is_aligned,
                    "length": self.length,
                    "sequence_count": self.sequence_count,
                    "data": self.data,
                    "metadata": self.metadata,
                    "selected": self.selected,
                    "import_id": self.import_id,
                    "run_id": self.run_id,
                }
            )

    @dataclass
    class DatasetSpec:
        name: str
        items: List[DatasetItemSpec] = field(default_factory=list)
        description: str = ""
        source: str = ""
        partition_scheme: Optional[str] = None
        summary: Dict[str, Any] = field(default_factory=dict)
        metadata: Dict[str, Any] = field(default_factory=dict)
        dataset_id: Optional[str] = None

        def validate(self) -> List[str]:
            problems = []
            if not self.name:
                problems.append("dataset has no name")
            if not self.items:
                problems.append("dataset %r has no items" % self.name)
            for index, item in enumerate(self.items):
                for problem in item.validate():
                    problems.append("item %d: %s" % (index, problem))
            return problems

    @dataclass
    class RunSpec:
        method: str
        tool: str = ""
        tool_version: str = ""
        command: List[str] = field(default_factory=list)
        parameters: Dict[str, Any] = field(default_factory=dict)
        input_paths: List[str] = field(default_factory=list)
        output_paths: List[str] = field(default_factory=list)
        status: str = "completed"
        cwd: str = ""
        log: str = ""
        seed: str = ""
        metadata: Dict[str, Any] = field(default_factory=dict)
        started_at: str = ""
        completed_at: str = ""

        def to_dict(self) -> Dict[str, Any]:
            return _jsonable(self.__dict__)

    @dataclass
    class ResultSpec:
        source: str
        datasets: List[DatasetSpec] = field(default_factory=list)
        artifacts: List[str] = field(default_factory=list)
        summary: Dict[str, Any] = field(default_factory=dict)
        warnings: List[str] = field(default_factory=list)
        schema: str = RESULT_SCHEMA
        tool: str = ""
        tool_version: str = ""
        seed: str = ""
        runs: List[RunSpec] = field(default_factory=list)

        def validate(self) -> List[str]:
            problems = []
            if self.schema != RESULT_SCHEMA:
                problems.append("unsupported result schema %r" % self.schema)
            if not self.source:
                problems.append("result has no source")
            if not self.datasets:
                problems.append("result has no datasets")
            for index, dataset in enumerate(self.datasets):
                for problem in dataset.validate():
                    problems.append("dataset %d: %s" % (index, problem))
            return problems

        def to_dict(self) -> Dict[str, Any]:
            return _jsonable(self.__dict__)

        def to_json(self, indent: int = 2) -> str:
            import json

            return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
