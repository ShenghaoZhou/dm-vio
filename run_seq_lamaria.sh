#!/bin/bash

# Arguments
SEQ_NAME=$1
DATA_DIR=${2:-data/lamaria/training}

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

CALIB="configs/lamaria/camera.txt"
IMU_CALIB="configs/lamaria/camchain.yaml"
SETTINGS="configs/lamaria/config.yaml"

# Prepare data for DM-VIO
python3 prepare_lamaria.py "$SEQ_NAME" --data_dir "$DATA_DIR"

IMG_FOLDER="$SEQ_PATH/img0"
if [ ! -d "$IMG_FOLDER" ]; then
    # Fallback if img0 symlink wasn't created
    IMG_FOLDER="$SEQ_PATH/asl_folder/$SEQ_NAME/aria/cam0/data"
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
    nogui=0 \
    useimu=0 \
    resultsPrefix="$OUT_DIR/"
