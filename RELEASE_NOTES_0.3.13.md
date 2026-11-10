# Device Availability Digest v0.3.13

## Home Presence status colors

- The top **Household presence** summary now uses the same colors as the Home Presence timeline: **Home** green, **Away** amber, **Unknown** grey, and **Unavailable** grey.
- The status labels in the summary use consistent capitalization and match the timeline.
- Other summary metrics retain their normal appearance.

## Unchanged behavior

- The Home Presence decision still requires **20 minutes** without any positive Home evidence before changing from Unknown to Away.
- GPS Person and trusted labeled Wi-Fi Home observations continue to take precedence immediately.
- No changes to device availability, stale-sensor diagnostics, notification delivery, or historical mode tracking.

## Upgrade

Update the Device Availability Digest custom integration through HACS and restart Home Assistant. The managed panel asset is loaded with the updated integration version.
