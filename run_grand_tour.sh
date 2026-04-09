#!/bin/bash

# Arguments
SEQ_NAME=$1
DATA_DIR=${2:-data/grand_tour}

if [ -z "$SEQ_NAME" ]; then
    echo "Usage: $0 <sequence_name> [data_dir]"
    exit 1
fi

SEQ_PATH="$DATA_DIR/$SEQ_NAME"

if [ ! -d "$SEQ_PATH" ]; then
    echo "Error: Directory $SEQ_PATH does not exist."
    exit 1
fi

OUT_DIR="$SEQ_PATH/res"
mkdir -p "$OUT_DIR"

# Paths to configs
# Prioritize configs in the sequence folder if they were generated/downloaded
CALIB="configs/grand_tour/camera.txt"
IMU_CALIB="configs/grand_tour/camchain.yaml"
if [ -f "$SEQ_PATH/camera.txt" ]; then
    CALIB="$SEQ_PATH/camera.txt"
    echo "Using sequence-specific camera calibration: $CALIB"
else
    CALIB="configs/grand_tour/camera.txt"
fi

if [ -f "$SEQ_PATH/camchain.yaml" ]; then
    IMU_CALIB="$SEQ_PATH/camchain.yaml"
    echo "Using sequence-specific IMU-camera calibration: $IMU_CALIB"
else
    IMU_CALIB="configs/grand_tour/camchain.yaml"
fi

SETTINGS="configs/grand_tour/config.yaml"


# Prepare data for DM-VIO
# This script currently expects times.txt and imu.txt to be present in $SEQ_PATH.
# If they are in zarr format in alphasense_imu.tar, this script needs further logic to extract them.
pixi run python3 prepare_grand_tour.py "$SEQ_NAME" --data_dir "$DATA_DIR"

IMG_FOLDER="$SEQ_PATH/img0"
if [ ! -d "$IMG_FOLDER" ]; then
    # Fallback to the original extracted folder if img0 symlink wasn't created
    IMG_FOLDER="$SEQ_PATH/images/alphasense_front_left"
fi

# Ensure times_dmvio.txt and imu_interpolated_dmvio.txt exist before running
if [ ! -f "$SEQ_PATH/times_dmvio.txt" ] || [ ! -f "$SEQ_PATH/imu_interpolated_dmvio.txt" ]; then
    echo "Error: Preparation failed. times_dmvio.txt or imu_interpolated_dmvio.txt not found."
    exit 1
fi

echo "Running dmvio_dataset on $SEQ_NAME with $CALIB and $IMU_CALIB"

build/bin/dmvio_dataset \
    files="$IMG_FOLDER" \
    tsFile="$SEQ_PATH/times_dmvio.txt" \
    imuFile="$SEQ_PATH/imu_interpolated_dmvio.txt" \
    calib="$CALIB" \
    imuCalib="$IMU_CALIB" \
    settingsFile="$SETTINGS" \
    mode=1 \
    preset=1 \
    useimu=1 \
    start=0 \
    benchmark_initializerSlackFactor=3.0 \
    nogui=1 \
    resultsPrefix="$OUT_DIR/"
