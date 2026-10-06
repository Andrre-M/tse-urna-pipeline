from pathlib import Path

import polars as pl

from tse_urna.transformation.bronze import build_bronze_batch
from tse_urna.transformation.compaction import compact_bronze_partition


def _write_log(path: Path, messages: list[str], *, invalid: bool = False) -> None:
    lines = [
        f"07/10/2018\t16:30:0{index}\tINFO\t1543882\tATUE\t{message}\t62AB14E695FE6D3D"
        for index, message in enumerate(messages)
    ]
    if invalid:
        lines.append("linha inválida")
    path.write_text("\n".join(lines) + "\n", encoding="latin-1")


def _metadata(source: str) -> dict[str, str | int]:
    return {
        "election_year": 2026,
        "pleito": "3220",
        "uf": "CE",
        "municipality": "13897",
        "zone": "0003",
        "section": "0444",
        "source_hash": source,
        "source_file": f"{source}.logjez",
    }


def test_bronze_batch_is_chunked_and_checkpointed(tmp_path: Path):
    first_log = tmp_path / "first.dat"
    second_log = tmp_path / "second.dat"
    _write_log(first_log, ["um", "dois"], invalid=True)
    _write_log(second_log, ["três"])
    output = tmp_path / "bronze" / "batch=abc"
    quarantine = tmp_path / "quarantine" / "batch=abc.jsonl"

    first = build_bronze_batch(
        logs=[(first_log, _metadata("a")), (second_log, _metadata("b"))],
        output_dir=output,
        quarantine_path=quarantine,
        target_rows=2,
    )
    second = build_bronze_batch(
        logs=[(first_log, _metadata("a")), (second_log, _metadata("b"))],
        output_dir=output,
        quarantine_path=quarantine,
        target_rows=2,
    )

    assert first == second
    assert first.valid_rows == 3
    assert first.rejected_rows == 1
    assert len(first.output_files) == 2
    assert sum(pl.read_parquet(path).height for path in first.output_files) == 3
    assert quarantine.read_text(encoding="utf-8").count("unparsed_line") == 1


def test_compaction_reuses_unchanged_partition(tmp_path: Path):
    input_dir = tmp_path / "bronze"
    for batch, value in [("a", 1), ("b", 2)]:
        path = input_dir / f"batch={batch}" / "part-00000.parquet"
        path.parent.mkdir(parents=True)
        pl.DataFrame({"value": [value]}).write_parquet(path)

    output_dir = tmp_path / "bronze_compacted"
    first = compact_bronze_partition(
        input_dir=input_dir, output_dir=output_dir, target_size_mb=10
    )
    second = compact_bronze_partition(
        input_dir=input_dir, output_dir=output_dir, target_size_mb=10
    )

    assert first == second
    assert len(first) == 1
    assert pl.read_parquet(first[0]).sort("value")["value"].to_list() == [1, 2]
