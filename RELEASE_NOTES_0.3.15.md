# Device Availability Digest v0.3.15

## Fix previously flagged control and status entities still reported stale

The v0.3.14 exclusion policy mistakenly preserved previously flagged entities
when they were `unknown` or `unavailable`. This allowed SMA power-limit
controls, sauna standby status and dishwasher programme progress to remain
listed as STALE indefinitely. The monitor now trusts the live entity registry
and current eligibility, rather than resurrecting old incidents.

The selector now considers the Home Assistant friendly/display and registry
original names, in addition to entity IDs, to recognize those operational
values when IDs do not include the display-name words.

When a control/status entity is excluded, active flags and undelivered queue
entries for it are removed **without manufacturing a CLEARED/recovered email**.
Existing diagnostic history remains intact.

Real measurements, including PM2.5 and measured SMA power, are still monitored;
unknown or unavailable on an eligible physical measurement remains meaningful.
The existing `stale_monitor_include` and `stale_monitor_ignore` labels
continue to override automatic selection.

## Upgrade

Update through Home Assistant HACS/Marketplace and restart HA. Open
Availability → Stale sensors and check the list after the next scan
(typically within 15 minutes). The kitchen PM2.5 stuck-low detection is unchanged
from v0.3.14.
