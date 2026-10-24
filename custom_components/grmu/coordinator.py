import logging
import urllib.parse
import re
import json
import aiohttp
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, URL_BASE, DEFAULT_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

def parse_float(value, default=0.0) -> float:
    """Безпечне перетворення рядка з комою у float."""
    if value is None:
        return default
    try:
        val_str = str(value).replace(",", ".").replace(" ", "").strip()
        return float(val_str)
    except (ValueError, TypeError):
        return default

class GrmuDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, email: str, password: str):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self.email = email
        self.password = password

    async def _async_update_data(self):
        jar = aiohttp.CookieJar(unsafe=True)
        async with aiohttp.ClientSession(cookie_jar=jar) as session:
            base_headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }

            try:
                # 1. GET /login
                async with session.get(f"{URL_BASE}/login", headers=base_headers) as resp:
                    if resp.status != 200:
                        raise UpdateFailed(f"Не вдалося відкрити сторінку входу. Код: {resp.status}")
                    html_text = await resp.text()

                inertia_version = None
                version_match = re.search(r'data-page=["\']({.*})["\']', html_text)
                if version_match:
                    try:
                        raw_json = version_match.group(1).replace('&quot;', '"')
                        page_data = json.loads(raw_json)
                        inertia_version = page_data.get("version")
                    except Exception:
                        pass

                if not inertia_version:
                    v_match = re.search(r'"version"\s*:\s*"([a-f0-9]+)"', html_text)
                    if v_match:
                        inertia_version = v_match.group(1)

                cookies = session.cookie_jar.filter_cookies(URL_BASE)
                xsrf_cookie = cookies.get("XSRF-TOKEN")
                
                inertia_headers = {
                    "User-Agent": base_headers["User-Agent"],
                    "X-Requested-With": "XMLHttpRequest",
                    "X-Inertia": "true",
                }

                if inertia_version:
                    inertia_headers["X-Inertia-Version"] = str(inertia_version)

                if xsrf_cookie:
                    inertia_headers["X-XSRF-TOKEN"] = urllib.parse.unquote(xsrf_cookie.value)

                # 2. POST /login
                post_headers = {**inertia_headers, "Content-Type": "application/json"}
                login_data = {
                    "email": self.email,
                    "password": self.password,
                    "remember": False,
                    "captcha": None,
                }

                async with session.post(
                    f"{URL_BASE}/login",
                    json=login_data,
                    headers=post_headers,
                    allow_redirects=False
                ) as resp:
                    location = resp.headers.get("Location", "")
                    if resp.status in (302, 303) and "/login" in location:
                        raise UpdateFailed("Помилка авторизації: перевірте email та пароль")

                    if resp.status not in (200, 302, 303):
                        raise UpdateFailed(f"Помилка авторизації (статус {resp.status})")

                cookies = session.cookie_jar.filter_cookies(URL_BASE)
                xsrf_cookie = cookies.get("XSRF-TOKEN")
                if xsrf_cookie:
                    inertia_headers["X-XSRF-TOKEN"] = urllib.parse.unquote(xsrf_cookie.value)

                # 3. GET / (головна сторінка)
                async with session.get(f"{URL_BASE}/", headers=inertia_headers) as resp:
                    if resp.status != 200:
                        raise UpdateFailed(f"Помилка отримання даних. Код: {resp.status}")
                    
                    data = await resp.json()
                    props = data.get("props", {})
                    auth = props.get("auth", {})
                    info = auth.get("info", {})
                    account = auth.get("account", {})

                    account_number = info.get("personal_account") or account.get("personal_account")

                    if not account_number:
                        raise UpdateFailed("Не вдалося отримати номер особового рахунку з відповіді")

                # 4. GET /counters (поточний стан лічильника)
                last_counter_val = 0.0
                last_counter_date = ""
                counter_serial = ""
                last_value_source = ""
                counter_slot = 0

                try:
                    async with session.get(f"{URL_BASE}/counters", headers=inertia_headers) as c_resp:
                        if c_resp.status == 200:
                            c_data = await c_resp.json()
                            counters_list = c_data if isinstance(c_data, list) else c_data.get("props", {}).get("counters", [])

                            if isinstance(counters_list, list) and len(counters_list) > 0:
                                c_info = counters_list[0]
                                last_counter_val = parse_float(c_info.get("LASTVALUE"))
                                last_counter_date = str(c_info.get("LASTVALUE_DATE", "")).strip()
                                counter_serial = str(c_info.get("COUNTER_SERIAL", "")).strip()
                                last_value_source = str(c_info.get("LASTVALUE_SOURCE", "")).strip()
                                counter_slot = c_info.get("COUNTER_SLOT", 0)
                except Exception as c_err:
                    _LOGGER.warning("Попередження: не вдалося завантажити /counters: %s", c_err)

                # 5. GET /counters/data/history
                consumption_history = []
                counter_history = []

                try:
                    # а) Початковий запит (поточний рік)
                    async with session.get(f"{URL_BASE}/counters/data/history", headers=inertia_headers) as h_resp:
                        if h_resp.status == 200:
                            h_data = await h_resp.json()
                            h_props = h_data.get("props", {})
                            
                            curr_consumption = h_props.get("consumptionHistory", [])
                            curr_counter = h_props.get("counterHistory", [])
                            years = h_props.get("years", [])

                            consumption_history.extend(curr_consumption)
                            counter_history.extend(curr_counter)

                            # Визначаємо попередній рік
                            prev_year = None
                            if isinstance(years, list) and len(years) > 1:
                                prev_year = years[1]
                            elif isinstance(years, list) and len(years) == 1:
                                prev_year = years[0] - 1

                            if prev_year:
                                # б) Історія споживання за попередній рік
                                url_cons = f"{URL_BASE}/counters/data/history?consumption_data_year={prev_year}"
                                async with session.get(url_cons, headers=inertia_headers) as p_resp:
                                    if p_resp.status == 200:
                                        p_data = await p_resp.json()
                                        p_props = p_data.get("props", {})
                                        prev_cons = p_props.get("consumptionHistory", [])

                                        existing_cons_keys = {(c.get("YEARIC"), c.get("MONTHIC")) for c in consumption_history}
                                        for pc in prev_cons:
                                            key = (pc.get("YEARIC"), pc.get("MONTHIC"))
                                            if key not in existing_cons_keys:
                                                consumption_history.append(pc)
                                                existing_cons_keys.add(key)

                                # в) Історія показників лічильника за попередній рік
                                url_cnt = f"{URL_BASE}/counters/data/history?counter_slot={counter_slot}&counter_data_year={prev_year}"
                                async with session.get(url_cnt, headers=inertia_headers) as p_cnt_resp:
                                    if p_cnt_resp.status == 200:
                                        p_cnt_data = await p_cnt_resp.json()
                                        p_cnt_props = p_cnt_data.get("props", {})
                                        prev_cnt = p_cnt_props.get("counterHistory", [])

                                        existing_cnt_keys = {(str(c.get("DATE")), parse_float(c.get("VALUE"))) for c in counter_history}
                                        for pc in prev_cnt:
                                            key = (str(pc.get("DATE")), parse_float(pc.get("VALUE")))
                                            if key not in existing_cnt_keys:
                                                counter_history.append(pc)
                                                existing_cnt_keys.add(key)

                except Exception as h_err:
                    _LOGGER.warning("Попередження: не вдалося завантажити /counters/data/history: %s", h_err)

                return {
                    "account_number": str(account_number),
                    "eic": str(info.get("eic_code", "")),
                    "address": str(info.get("address", "")),
                    "balance": parse_float(info.get("rzp_balance", 0.0)),
                    "consumption": parse_float(info.get("consumption_v", 0.0)),
                    "consumption_month": str(info.get("consumption_month", "")),
                    "rate": parse_float(info.get("tariff", 1.788)),
                    "distr_month_v": parse_float(info.get("distr_month_v", 0.0)),
                    "distr_year_v": parse_float(info.get("distr_year_v", 0.0)),
                    "distr_sum": parse_float(info.get("distr_sum", 0.0)),
                    "period": str(info.get("period", "")),
                    "precalc_month_v": parse_float(info.get("precalc_month_v", 0.0)),
                    "precalc_year_v": parse_float(info.get("precalc_year_v", 0.0)),
                    "precalc_year": str(info.get("precalc_year", "2027")),
                    "last_counter_value": last_counter_val,
                    "last_counter_date": last_counter_date,
                    "counter_serial": counter_serial,
                    "last_value_source": last_value_source,
                    "consumption_history": consumption_history,
                    "counter_history": counter_history,
                }

            except Exception as err:
                _LOGGER.exception("Деталі помилки підключення до ГРМУ: %s", err)
                raise UpdateFailed(f"Помилка з'єднання: {err}") from err