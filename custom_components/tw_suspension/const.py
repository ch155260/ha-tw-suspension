"""Constants for the tw_suspension integration."""

DOMAIN = "tw_suspension"

DGPA_URL = "https://www.dgpa.gov.tw/typh/daily/nds.html"
NLSC_COUNTY_URL = "https://api.nlsc.gov.tw/other/ListCounty"
NLSC_TOWN_URL = "https://api.nlsc.gov.tw/other/ListTown1"

CONF_CITY = "city"
CONF_DISTRICT = "district"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_VERIFY_SSL = "verify_ssl"

DEFAULT_SCAN_INTERVAL = 30  # minutes
MIN_SCAN_INTERVAL = 10  # minutes
CACHE_SECONDS = 60
REQUEST_TIMEOUT = 10

ALL_DISTRICTS = "__all__"
DEFAULT_VERIFY_SSL = False  # DGPA 憑證缺少 Subject Key Identifier，嚴格驗證會失敗
