// Keep the managed dashboard and backend contract wired across releases.
const assert=require("node:assert/strict");
const fs=require("node:fs");
const js=fs.readFileSync("custom_components/device_availability_digest/www/managed-panel.js","utf8");
const api=fs.readFileSync("custom_components/device_availability_digest/diagnostics_api.py","utf8");
const monitor=fs.readFileSync("custom_components/device_availability_digest/stale_monitor.py","utf8");
const rules=fs.readFileSync("custom_components/device_availability_digest/stale_logic.py","utf8");
const init=fs.readFileSync("custom_components/device_availability_digest/__init__.py","utf8");
assert.match(js, /Stale sensors/);
assert.match(js, /All monitored/);
assert.match(js, /_stale\(grid,data\)/);
assert.match(js, /stale_monitor_watch_value/);
assert.match(js, /last_reported/);
assert.match(api, /"stale": \(monitor\.stale\.snapshot\(\)/);
assert.match(monitor, /async def scan\(self, send_digest: bool = False\)/);
assert.match(rules, /"no_report"/);
assert.match(init, /async_track_time_change/);
assert.match(init, /hour in \(8, 20\)/);
console.log("Stale monitor dashboard and backend contract verified.");
