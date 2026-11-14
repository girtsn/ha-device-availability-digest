"""Constants for Device Availability Digest."""
DOMAIN = "device_availability_digest"
CONF_NOTIFY = "notify_entity"
CONF_EMAIL_SUBJECT_PREFIX = "email_subject_prefix"
DEFAULT_EMAIL_SUBJECT_PREFIX = "[HASS]"
CONF_OFFLINE_MINUTES = "offline_minutes"
CONF_WINDOW_MINUTES = "window_minutes"
CONF_EXCLUDED_ENTITIES = "excluded_entities"
CONF_EXCLUDED_DEVICE_ANCHORS = "excluded_device_entities"
CONF_CONNECTIVITY_ENTITIES = "connectivity_entities"
CONF_AUTO_EXCLUDE_TVS = "auto_exclude_tvs"
CONF_AUTO_EXCLUDE_CAST = "auto_exclude_cast"
DEFAULT_OFFLINE_MINUTES = 5
DEFAULT_WINDOW_MINUTES = 20

DOMAINS = (
    "camera", "light", "climate", "switch",
    "binary_sensor", "sensor", "media_player",
    "alarm_control_panel",
)
UNHEALTHY_CONNECTION = {"off", "unknown", "unavailable"}
