from controller.runtime_probe import header_height, local_block_height, parse_pair, parse_size


def test_parse_size_handles_docker_units():
    assert parse_size("12.5MiB") == 13107200
    assert parse_size("1.5 GB") == 1500000000


def test_parse_pair_handles_docker_io_values():
    assert parse_pair("1.0MiB / 2.0MiB") == (1048576, 2097152)


def test_local_block_height_prefers_sync_info_current_height_over_tip():
    status = {
        "tip": {"height": 3_075_000},
        "sync_info": {"current_height": 120, "highest_height": 3_075_000},
    }

    assert local_block_height(status) == 120
    assert header_height(status) == 3_075_000


def test_local_block_height_falls_back_to_tip_when_sync_info_is_absent():
    status = {"tip": {"height": 3_075_000}}

    assert local_block_height(status) == 3_075_000
    assert header_height(status) == 3_075_000
