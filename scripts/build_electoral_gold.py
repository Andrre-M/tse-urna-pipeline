from __future__ import annotations

import argparse
from pathlib import Path

from tse_urna.transformation.electoral_gold import (
    ElectoralSourceFiles,
    build_electoral_gold,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    source_dir = args.source_dir
    sources = ElectoralSourceFiles(
        state_votes=source_dir / "votacao_secao_2026_CE.csv",
        presidential_votes=source_dir / "votacao_secao_2026_BR.csv",
        state_section_detail=source_dir / "detalhe_votacao_secao_2026_CE.csv",
        presidential_section_detail=source_dir / "detalhe_votacao_secao_2026_BR.csv",
        electorate_profile=source_dir / "perfil_eleitor_secao_2026_CE.csv",
        state_candidates=source_dir / "consulta_cand_2026_CE.csv",
        presidential_candidates=source_dir / "consulta_cand_2026_BR.csv",
    )
    result = build_electoral_gold(sources=sources, output_dir=args.output_dir)
    print(
        f"municipalities={result.municipalities} sections={result.sections} "
        f"registered_electors={result.registered_electors}"
    )
    for table, rows in result.row_counts.items():
        print(f"{table}={rows}")


if __name__ == "__main__":
    main()
