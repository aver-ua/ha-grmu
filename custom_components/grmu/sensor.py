from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

SENSOR_TYPES = {
    "balance": {
        "name": "Баланс",
        "unit": "UAH",
        "device_class": SensorDeviceClass.MONETARY,
        "state_class": None,
        "icon": "mdi:currency-uah",
    },
    "last_counter_value": {
        "name": "Останні показники лічильника",
        "unit": "m³",
        "device_class": SensorDeviceClass.GAS,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:counter",
    },
    "consumption": {
        "name": "Споживання за місяць",
        "unit": "m³",
        "device_class": SensorDeviceClass.GAS,
        "state_class": SensorStateClass.TOTAL,
        "icon": "mdi:fire",
    },
    "rate": {
        "name": "Тариф",
        "unit": "UAH/m³",
        "device_class": None,
        "state_class": None,
        "icon": "mdi:cash-multiple",
    },
    "distr_sum": {
        "name": "Плата за розподіл (місячна)",
        "unit": "UAH",
        "device_class": SensorDeviceClass.MONETARY,
        "state_class": None,
        "icon": "mdi:receipt-text-outline",
    },
    "distr_month_v": {
        "name": "Замовлена потужність (місячна)",
        "unit": "m³",
        "device_class": SensorDeviceClass.GAS,
        "state_class": None,
        "icon": "mdi:chart-line",
    },
    "distr_year_v": {
        "name": "Замовлена потужність (річна)",
        "unit": "m³",
        "device_class": SensorDeviceClass.GAS,
        "state_class": None,
        "icon": "mdi:chart-histogram",
    },
    "precalc_month_v": {
        "name": "Замовлена потужність наступний рік (місячна)",
        "unit": "m³",
        "device_class": SensorDeviceClass.GAS,
        "state_class": None,
        "icon": "mdi:crystal-ball",
    },
    "precalc_year_v": {
        "name": "Замовлена потужність наступний рік (річна)",
        "unit": "m³",
        "device_class": SensorDeviceClass.GAS,
        "state_class": None,
        "icon": "mdi:calendar-blank-outline",
    },
}

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]

    device_info = DeviceInfo(
        identifiers={(DOMAIN, coordinator.data["account_number"])},
        name=f"Особовий рахунок {coordinator.data['account_number']}",
        manufacturer="ГРМУ",
        model="Київська філія",
    )

    entities = [
        GrmuSensor(coordinator, key, meta, device_info)
        for key, meta in SENSOR_TYPES.items()
    ]

    async_add_entities(entities)

class GrmuSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, key, meta, device_info):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"ГРМУ {meta['name']}"
        self._attr_unique_id = f"{coordinator.data['account_number']}_{key}"
        self._attr_native_unit_of_measurement = meta["unit"]
        self._attr_device_class = meta["device_class"]
        self._attr_state_class = meta["state_class"]
        self._attr_icon = meta["icon"]
        self._attr_device_info = device_info

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)

    @property
    def extra_state_attributes(self):
        if self._key == "balance":
            return {
                "eic": self.coordinator.data.get("eic"),
                "address": self.coordinator.data.get("address"),
                "account_number": self.coordinator.data.get("account_number"),
                "period": self.coordinator.data.get("period"),
            }
        elif self._key == "last_counter_value":
            return {
                "last_counter_date": self.coordinator.data.get("last_counter_date"),
                "counter_serial": self.coordinator.data.get("counter_serial"),
                "last_value_source": self.coordinator.data.get("last_value_source"),
                "counter_history": self.coordinator.data.get("counter_history"),
            }
        elif self._key == "consumption":
            return {
                "consumption_month": self.coordinator.data.get("consumption_month"),
                "consumption_history": self.coordinator.data.get("consumption_history"),
            }
        elif self._key in ("precalc_month_v", "precalc_year_v"):
            return {
                "precalc_year": self.coordinator.data.get("precalc_year"),
            }
        return {}