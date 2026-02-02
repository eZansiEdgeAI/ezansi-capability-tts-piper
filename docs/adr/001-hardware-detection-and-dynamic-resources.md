# ADR-001: Hardware Detection and Dynamic Resource Configuration

Status: Accepted
Date: 2026-02-02

## Context

Early versions of this capability used fixed “hardware profiles” and multiple compose presets.

That approach caused operational friction:

- Users had to pick the correct preset for their device (Pi 4 vs Pi 5, RAM tiers, etc.).
- The same device can have very different available resources depending on what else is running.
- We want a single compose file to “just work” on edge hardware.

At the same time, we still want to avoid overcommitting resources on small devices.

## Decision

1. The capability performs **runtime hardware detection** at startup to report:
   - architecture
   - total system memory (RAM)
   - CPU cores
   - best-effort GPU presence

2. The project standardizes a simple **resource hint policy** based on available RAM:

- **RAM allocation**: $\min(600, \max(300, 0.5 \times \text{RAM\_total}))$ MB
- **CPU allocation**: 1 core for small devices, otherwise 2 cores

3. A **preflight script** (`scripts/configure-hardware.sh`) can optionally write a `.env` file
   with `podman-compose` resource constraints derived from the same policy:

- `TTS_CPU_LIMIT`
- `TTS_MEMORY_LIMIT`
- (optional) reservation values

Preflight is best-effort: the stack should still start without it.

## Consequences

### Positive

- One compose file can support heterogeneous edge hardware.
- Resource selection is aligned to the *actual host*, not a guessed profile.
- Users can override behavior by editing `.env`.

### Trade-offs

- This is heuristic and intentionally conservative; it is not a full scheduler.
- GPU detection is best-effort and may under-detect accelerators.

## Alternatives considered

- Maintain static profile compose presets: rejected due to UX friction.
- Auto-tune aggressively (use most RAM/cores): rejected to reduce risk on constrained devices.
