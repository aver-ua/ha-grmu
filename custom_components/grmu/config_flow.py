import logging
import voluptuous as vol
from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD
from .coordinator import GrmuDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)

class GrmuConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            coordinator = GrmuDataUpdateCoordinator(
                self.hass,
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
            )
            try:
                data = await coordinator._async_update_data()
                await self.async_set_unique_id(data["account_number"])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Рахунок {data['account_number']}",
                    data=user_input,
                )
            except Exception as err:
                _LOGGER.error("Помилка авторизації/підключення ГРМУ: %s", err, exc_info=True)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )