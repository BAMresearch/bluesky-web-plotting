# OPERATIONS.md — Running & Deploying the Timeline UI (v1)

This document describes how the timeline UI is expected to run in practice and what operational knobs matter.

It intentionally avoids deep deployment specifics (k8s/systemd/etc.) and focuses on the conceptual topology and configuration.

---

## 1. Typical deployment topology

### 1.1. Single beamline / instrument

- **RunEngine (RE)** runs on the control machine.
- RE publishes documents via **ZMQ PUB**.
- The UI (Dash app) subscribes via **ZMQ SUB** and updates immediately.
- The UI also polls the central (or local) **Tiled** server for historical runs.

**Result:** Operators see both history + current acquisition.

### 1.2. Multi-beamline monitoring

- Prefer relying on a **central Tiled** server as the source of truth.
- Avoid subscribing to many independent ZMQ streams from multiple RunEngines (complex, brittle, firewall/network issues).
- Accept slightly higher latency due to polling and indexing.

**Result:** More stable cross-beamline monitoring, with less operational complexity.

---

## 2. What the UI shows

- **Timeline lanes**: derived from track `group_by` (e.g. `start.plan_name`, `start.proposal_id`).
- **Clips**: runs from `start.time` to `stop.time`, or to “now” if running.
- **Selection**: click a clip to highlight it.
- **Playhead**: click position becomes the cursor time, drawn as a vertical line.

---

## 3. Configuration knobs that matter operationally

### 3.1. Live (ZMQ)

- `sources.live.enabled`
- `sources.live.zmq_address`

**Notes**
- If the live badge is “disconnected”, the UI may still function via Tiled-only mode.
- ZMQ pub/sub is low-latency but not durable; drops can occur.

### 3.2. Tiled

- `sources.tiled.enabled`
- `sources.tiled.uri`
- `sources.tiled.lookback_hours`  
  Limits server-side query window (critical for large catalogs).
- `sources.tiled.poll_interval_ms`  
  Controls how often the UI syncs new/updated runs.
- `sources.tiled.include_incomplete`  
  Include runs missing a stop doc.

### 3.3. Timeline window vs indexing lookback

- `timeline.default_window_hours`  
  UI view window (how much is shown by default).
- `sources.tiled.lookback_hours`  
  Index window (how much data is fetched/considered from server).

Recommendation:
- `lookback_hours >= default_window_hours` so the UI always has enough data.

---

## 4. Status badges and expected failure modes

### 4.1. Live badge

- Connected when documents are being received.
- Disconnected can mean:
  - publisher not running
  - wrong address/port
  - network/firewall issues

### 4.2. Tiled badge

- Connected when the last poll succeeded.
- Common issues:
  - URI incorrect
  - authentication/permissions
  - server downtime

---

## 5. Performance considerations

- Always rely on **server-side time filtering** when polling Tiled.
- Prefer “Tiled-only mode” for large, multi-beamline views.
- Keep plot updates coarse-grained (e.g. update the timeline once every few hundred ms for running clips; poll Tiled every 1–10 seconds depending on scale).

---

## 6. Security note (high level)

- ZMQ is typically used on trusted networks.
- For cross-beamline or remote usage, prefer central Tiled access with authentication rather than opening multiple ZMQ endpoints broadly.

