"""Stardew compatibility wrapper around the shared bounded native input host."""
from smb3_agent.native_input import MacBoundedInputDriver
from smb3_agent.native_input import time as time
from smb3_agent.native_input import threading as threading
from smb3_agent.stardew_adapter import StardewAdapterError

class MacOrdinaryInputDriver(MacBoundedInputDriver):
    error_type = StardewAdapterError
    aim_purposes = frozenset({"water_crop", "harvest_crop", "plant_seed", "clear_debris", "select_farm_item"})
    gameplay_purposes = aim_purposes | {"navigate"}
