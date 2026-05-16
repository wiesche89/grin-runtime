from controller.runtime_probe import parse_pair, parse_size


def test_parse_size_handles_docker_units():
    assert parse_size("12.5MiB") == 13107200
    assert parse_size("1.5 GB") == 1500000000


def test_parse_pair_handles_docker_io_values():
    assert parse_pair("1.0MiB / 2.0MiB") == (1048576, 2097152)
