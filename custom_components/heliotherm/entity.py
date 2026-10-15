"""Base entity for the Heliotherm integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import override

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import HeliothermCoordinator


@dataclass(frozen=True, kw_only=True)
class HeliothermEntityDescription(EntityDescription):
    """Describe an entity reading one component of the heat pump."""

    component: str
    """The device attribute that polls the entity's registers, e.g.
    ``temperatures``; its name in the update report decides availability."""


class HeliothermEntity(CoordinatorEntity[HeliothermCoordinator]):
    """Define a base entity held by the coordinator."""

    _attr_has_entity_name = True
    entity_description: HeliothermEntityDescription

    def __init__(
        self,
        coordinator: HeliothermCoordinator,
        description: HeliothermEntityDescription,
    ) -> None:
        """Initialize the entity onto the heat pump's device."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        self._attr_device_info: dr.DeviceInfo | None = coordinator.device_info

    @property
    @override
    def available(self) -> bool:
        """Whether the component this entity reads answered the last poll."""
        if not super().available or self.coordinator.data is None:
            return False
        return self.entity_description.component not in self.coordinator.data.failed
