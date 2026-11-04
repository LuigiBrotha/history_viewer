from datetime import date

import numpy as np

from tools.build_atlas_overlays import (
    LEGEND,
    TRANSPARENT,
    map_date,
    recolor,
    sample_smoothed,
    source_position,
)


def test_map_date_reads_the_month_from_the_file_name():
    assert map_date("Ww2_allied_axis_1941_dec.png") == date(1941, 12, 1)
    assert map_date("Ww2_allied_axis_1939_sep.PNG") == date(1939, 9, 1)


def test_recolor_maps_each_source_colour_to_its_soft_tint():
    source = np.array([[[0, 0, 0], [0x2a, 0xac, 0xf6], [0xf2, 0x0d, 0x0d], [0xe0, 0xe0, 0xe0], [255, 255, 255]]])

    indexes = recolor(source)

    assert [LEGEND[i - 1]["name"] for i in indexes[0][:4]] == ["As", "Westerse geallieerden", "Sovjet-Unie", "Neutraal"]
    assert indexes[0][4] == TRANSPARENT


def test_recolor_maps_antialiased_pixels_to_the_nearest_colour():
    source = np.array([[[0, 0xa8, 0xff], [0x7f, 0x7f, 0x7f]]])

    indexes = recolor(source)

    assert LEGEND[indexes[0][0] - 1]["name"] == "Westerse geallieerden"
    assert indexes[0][1] != TRANSPARENT


def test_source_position_places_known_points_on_the_source_map():
    # Measured on the source image: London and Cape Town.
    x, y = source_position(np.array([51.5]), np.array([0.0]))
    assert 690 < x[0] < 720
    assert 120 < y[0] < 160
    x, y = source_position(np.array([-33.9]), np.array([18.4]))
    assert 760 < x[0] < 800
    assert 500 < y[0] < 540


def test_source_position_wraps_around_the_central_meridian():
    x_east, _ = source_position(np.array([0.0]), np.array([-170.0]))
    x_west, _ = source_position(np.array([0.0]), np.array([-171.0]))
    assert x_east[0] < 100 or x_east[0] > 1380
    assert abs(x_east[0] - x_west[0]) > 0


def test_sample_smoothed_closes_a_thin_white_border_within_a_bloc():
    indexes = np.ones((9, 9), dtype=int)
    indexes[:, 4] = TRANSPARENT

    sampled = sample_smoothed(indexes, np.full((1, 1), 4.0), np.full((1, 1), 4.0))

    assert sampled[0, 0] == 1


def test_sample_smoothed_keeps_a_wide_area_of_sea():
    indexes = np.ones((21, 21), dtype=int)
    indexes[:, 10:] = TRANSPARENT

    sampled = sample_smoothed(indexes, np.array([[2.0, 18.0]]), np.array([[10.0, 10.0]]))

    assert sampled[0, 0] == 1
    assert sampled[0, 1] == TRANSPARENT


def test_sample_smoothed_is_transparent_outside_the_source():
    indexes = np.ones((5, 5), dtype=int)

    sampled = sample_smoothed(indexes, np.array([[-50.0]]), np.array([[2.0]]))

    assert sampled[0, 0] == TRANSPARENT
