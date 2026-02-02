# ADR-001: Hardware Detection and Dynamic Resource Configuration

## Status

Accepted

## Date

2026-02-02

## Context

The eZansi TTS capability previously used a static hardware profile approach where resource requirements (RAM, CPU cores, accelerator type) were hardcoded in the `capability.json` file. This approach had several limitations:

1. **Inflexibility**: The same configuration was used regardless of the actual hardware available on the deployment target
2. **Poor Resource Utilization**: Could under-utilize powerful systems or fail on resource-constrained devices
3. **Manual Configuration**: Required manual adjustment of configuration files for different deployment scenarios
4. **Limited Platform Support**: Hardcoded "target_platform" field (e.g., "Raspberry Pi 4/5") didn't reflect the actual diversity of deployment targets

The eZansi platform-core repository and other capabilities demonstrate a need for more intelligent, adaptive resource management that can detect and respond to the actual hardware capabilities of the deployment environment.

## Decision

We have implemented an automatic hardware detection and dynamic resource configuration system with the following components:

### 1. Hardware Detection Module (`src/hardware_detection.py`)

A dedicated Python module that detects:
- **System Architecture**: Uses `platform.machine()` to detect x86_64, aarch64, armv7l, etc.
- **Available RAM**: Reads from `/proc/meminfo` (Linux) to determine available memory in MB
- **CPU Cores**: Uses `os.cpu_count()` to detect the number of available CPU cores
- **GPU Availability**: Checks for NVIDIA CUDA (`nvidia-smi`), AMD ROCm (`rocm-smi`), and Intel OpenVINO

### 2. Dynamic Resource Recommendation

The system calculates recommended resource allocation based on detected hardware:
- **RAM Allocation**: Uses 50% of available RAM, with a minimum of 300MB and maximum of 600MB
- **CPU Allocation**: Allocates 1-2 cores based on system capacity (1 core for ≤3 cores, 2 cores for ≥4 cores)
- **Accelerator**: Automatically detects and configures GPU acceleration when available

### 3. Container Resource Limits

Modified `podman-compose.yml` to use environment-based resource configuration:
- Supports `deploy.resources.limits` and `deploy.resources.reservations`
- Uses environment variables with sensible defaults: `TTS_CPU_LIMIT`, `TTS_MEMORY_LIMIT`, etc.
- Allows manual override when needed

### 4. Configuration Script (`scripts/configure-hardware.sh`)

A shell script that:
- Detects system hardware using standard Linux tools
- Calculates appropriate resource limits
- Generates a `.env` file with configuration for podman-compose
- Can be run before deployment to auto-configure the service

### 5. Runtime API Exposure

The FastAPI application now exposes detected hardware information:
- `/health` endpoint returns detected hardware in the response
- `/.well-known/capability.json` endpoint includes both recommended resources and actual detected hardware
- Provides transparency for monitoring and debugging

## Consequences

### Positive

1. **Portability**: The same container image works across different architectures (x86_64, aarch64, armv7l) and hardware configurations
2. **Optimal Resource Usage**: Automatically adapts to available resources, preventing over-allocation on constrained devices and under-utilization on powerful systems
3. **Simplified Deployment**: Users run a single configuration script instead of manually editing configuration files
4. **Better Observability**: Hardware information is exposed via API endpoints for monitoring and debugging
5. **Future-Proof**: Easy to extend with additional hardware detection (e.g., NPU, specific accelerator versions)
6. **Alignment with Platform**: Consistent with the eZansi platform-core approach to capability management

### Negative

1. **Complexity**: Adds code complexity compared to static configuration
2. **Detection Failures**: Hardware detection might fail in unusual environments (e.g., containers with restricted /proc access)
3. **Platform-Specific**: Detection logic is Linux-specific; would need modification for other operating systems
4. **Startup Overhead**: Small overhead from hardware detection at application startup (negligible in practice)

### Mitigations

1. **Graceful Fallbacks**: All detection functions have fallback values if detection fails
2. **Manual Override**: Users can still manually configure resources via environment variables
3. **Clear Documentation**: README provides guidance on both automatic and manual configuration
4. **Validation Testing**: Hardware detection is validated on the build system before deployment

## Alternatives Considered

### 1. Profile-Based Selection

Create multiple predefined profiles (e.g., "raspberry-pi", "desktop", "server") and let users select one.

**Rejected because**: 
- Still requires manual selection
- Profiles become outdated as hardware evolves
- Doesn't handle the continuum of hardware capabilities well

### 2. Container Runtime Detection Only

Rely solely on container runtime (Podman/Docker) to manage resources without application-level detection.

**Rejected because**:
- Application wouldn't know its resource constraints for optimization
- Less visibility for users and monitoring systems
- Can't adapt application behavior based on available resources

### 3. External Configuration Service

Use an external service or database to store and retrieve hardware profiles.

**Rejected because**:
- Adds external dependencies for edge deployments
- Over-engineered for the current use case
- Reduces deployment simplicity

## References

- eZansi platform-core repository patterns
- Linux `/proc/meminfo` documentation
- Docker Compose resource limits specification
- Piper TTS resource requirements: https://github.com/rhasspy/piper

## Notes

- The `.env` file generated by the configuration script is added to `.gitignore` as it contains system-specific configuration
- Future enhancements could include:
  - Detection of specific accelerator capabilities (CUDA compute capability, etc.)
  - Model selection based on available resources
  - Adaptive quality settings based on hardware
  - Integration with Kubernetes resource requests/limits
