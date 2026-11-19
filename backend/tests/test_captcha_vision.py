from app.services.captcha_vision import parse_cells


def test_parse_cells_reads_the_list_and_drops_out_of_range():
    assert parse_cells("[2, 5, 9]", 9) == [2, 5, 9]
    assert parse_cells("Cells: [3, 3, 12, 0]", 9) == [3]
    assert parse_cells("[]", 9) == []
    assert parse_cells("2 and 7", 9) == [2, 7]
    assert parse_cells("", 16) == []
