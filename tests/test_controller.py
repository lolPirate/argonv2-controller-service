from argonv2_controller.config import FanConfig, FanPoint
from argonv2_controller.controller import FanCurveController


def make_controller() -> FanCurveController:
    return FanCurveController(
        FanConfig(
            hysteresis_c=3.0,
            minimum_change_percent=1,
            curve=(
                FanPoint(50, 20),
                FanPoint(55, 35),
                FanPoint(60, 60),
                FanPoint(65, 100),
            ),
        )
    )


def test_below_first_threshold_is_off():
    controller = make_controller()
    assert controller.decide(49.9).speed_percent == 0


def test_rises_immediately():
    controller = make_controller()
    assert controller.decide(55.0).speed_percent == 35
    assert controller.decide(60.0).speed_percent == 60


def test_hysteresis_prevents_threshold_hunting():
    controller = make_controller()

    assert controller.decide(55.0).speed_percent == 35
    assert controller.decide(54.0).speed_percent == 35
    assert controller.decide(52.1).speed_percent == 35

    # Below 55 - 3, drop to previous curve level (20%).
    assert controller.decide(51.9).speed_percent == 20


def test_can_fall_all_the_way_to_off():
    controller = make_controller()
    assert controller.decide(65.0).speed_percent == 100
    assert controller.decide(40.0).speed_percent == 0
