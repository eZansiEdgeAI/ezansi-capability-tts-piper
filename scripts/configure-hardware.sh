#!/bin/bash
# Configure hardware resources for TTS capability
# This script detects system hardware and sets appropriate resource limits

set -e

echo "Detecting system hardware..."

# Detect architecture
ARCH=$(uname -m)
echo "Architecture: $ARCH"

# Detect available RAM in MB
if [ -f /proc/meminfo ]; then
    TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    TOTAL_RAM_MB=$((TOTAL_RAM_KB / 1024))
    echo "Total RAM: ${TOTAL_RAM_MB} MB"
else
    TOTAL_RAM_MB=1024
    echo "Could not detect RAM, assuming: ${TOTAL_RAM_MB} MB"
fi

# Detect CPU cores
CPU_CORES=$(nproc 2>/dev/null || echo "1")
echo "CPU Cores: $CPU_CORES"

# Detect GPU
GPU_TYPE="none"
if command -v nvidia-smi &> /dev/null; then
    if nvidia-smi &> /dev/null; then
        GPU_TYPE="cuda"
    fi
elif command -v rocm-smi &> /dev/null; then
    if rocm-smi &> /dev/null; then
        GPU_TYPE="rocm"
    fi
elif [ -d "/opt/intel/openvino" ] || [ -n "$INTEL_OPENVINO_DIR" ]; then
    GPU_TYPE="openvino"
fi
echo "GPU Type: $GPU_TYPE"

# Calculate recommended resources
# Use 50% of available RAM, minimum 300MB, maximum 600MB
RECOMMENDED_RAM=$((TOTAL_RAM_MB / 2))
if [ $RECOMMENDED_RAM -lt 300 ]; then
    RECOMMENDED_RAM=300
fi
if [ $RECOMMENDED_RAM -gt 600 ]; then
    RECOMMENDED_RAM=600
fi

# Use 1-2 CPU cores based on availability
RECOMMENDED_CPU=1
if [ $CPU_CORES -ge 4 ]; then
    RECOMMENDED_CPU=2
fi

echo ""
echo "Recommended Configuration:"
echo "  CPU Limit: ${RECOMMENDED_CPU}.0"
echo "  Memory Limit: ${RECOMMENDED_RAM}M"
echo "  CPU Reservation: 0.5"
echo "  Memory Reservation: 300M"

# Create .env file for docker-compose
ENV_FILE=".env"
cat > "$ENV_FILE" << EOF
# Auto-generated hardware configuration
# Generated on: $(date)

# Detected Hardware
DETECTED_ARCH=$ARCH
DETECTED_RAM_MB=$TOTAL_RAM_MB
DETECTED_CPU_CORES=$CPU_CORES
DETECTED_GPU=$GPU_TYPE

# Resource Limits for Container
TTS_CPU_LIMIT=${RECOMMENDED_CPU}.0
TTS_MEMORY_LIMIT=${RECOMMENDED_RAM}M
TTS_CPU_RESERVATION=0.5
TTS_MEMORY_RESERVATION=300M
EOF

echo ""
echo "Configuration saved to $ENV_FILE"
echo "You can now run: podman-compose up -d"
