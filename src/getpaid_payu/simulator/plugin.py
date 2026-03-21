"""PayU simulator plugin factory."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from typing import Any

from getpaid_simulator.spi import SIMULATOR_PLUGIN_API_VERSION
from getpaid_simulator.spi import SimulatorProviderPlugin

from getpaid_payu.simulator.routes import cancel_order
from getpaid_payu.simulator.routes import capture_order
from getpaid_payu.simulator.routes import create_order
from getpaid_payu.simulator.routes import create_refund
from getpaid_payu.simulator.routes import get_order_info
from getpaid_payu.simulator.routes import oauth_endpoint
from getpaid_payu.simulator.routes import payu_authorize_get
from getpaid_payu.simulator.routes import payu_authorize_post
from getpaid_payu.simulator.routes import test_protected_endpoint
from getpaid_payu.simulator.transitions import PAYU_TRANSITIONS


if TYPE_CHECKING:
    from collections.abc import Mapping


def load_provider_config(
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environment = env or os.environ
    return {
        "second_key": environment.get(
            "SIMULATOR_PAYU_SECOND_KEY",
            "b6ca15b0d1020e8094d9b5f8d163db54",
        ),
    }


def get_plugin() -> SimulatorProviderPlugin:
    return SimulatorProviderPlugin(
        api_version=SIMULATOR_PLUGIN_API_VERSION,
        slug="payu",
        display_name="PayU",
        api_handlers=(
            oauth_endpoint,
            test_protected_endpoint,
            create_order,
            get_order_info,
            cancel_order,
            capture_order,
            create_refund,
        ),
        ui_handlers=(payu_authorize_get, payu_authorize_post),
        transitions=PAYU_TRANSITIONS,
        load_config=load_provider_config,
        authorize_path_template="/sim/payu/authorize/{entity_id}",
    )
