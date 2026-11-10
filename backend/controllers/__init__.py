from backend.controllers.adaptive import AdaptiveVACController
from backend.controllers.fixed_time import FixedTimeController
from backend.controllers.max_pressure import MaxPressureController

CONTROLLERS = {
    FixedTimeController.name: FixedTimeController,
    AdaptiveVACController.name: AdaptiveVACController,
    MaxPressureController.name: MaxPressureController,
}


def make_controller(name: str, params: dict | None = None):
    if name not in CONTROLLERS:
        raise ValueError(f"Unknown controller '{name}'. Choose from {list(CONTROLLERS)}")
    return CONTROLLERS[name](params)
