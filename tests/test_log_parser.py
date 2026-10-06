from datetime import datetime

from tse_urna.parsing.log_parser import parse_line


def test_parse_tab_delimited_line():
    line = (
        "07/10/2018\t16:30:03\tINFO\t1543882\tATUE\t"
        "Iniciando aplicação - Simulado - 1º turno\t62AB14E695FE6D3D\n"
    )
    event = parse_line(line, 1)
    assert event is not None
    assert event.event_timestamp == datetime(2018, 10, 7, 16, 30, 3)
    assert event.ue_id == "1543882"
    assert event.application == "ATUE"
    assert event.message_raw == "Iniciando aplicação - Simulado - 1º turno"


def test_parse_space_fallback_line():
    line = "07/10/2018 16:29:46 ALERTA 1543882 GAP Urna não testada 9AB0FB1BEB8DBDA4"
    event = parse_line(line, 2)
    assert event is not None
    assert event.severity == "ALERTA"
    assert event.message_raw == "Urna não testada"


def test_unparseable_line_returns_none():
    assert parse_line("linha inválida", 3) is None
