#!/bin/bash

# Arguments
SEQ_NAME=$1
DATA_DIR=${2:-data/uzhfpv}

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

CALIB="configs/uzhfpv/camera.txt"
IMU_CALIB="configs/uzhfpv/camchain.yaml"

if [[ "$SEQ_NAME" == *"indoor_45"* ]]; then
    CALIB="configs/uzhfpv/camera45.txt"
    IMU_CALIB="configs/uzhfpv/camchain_indoor45.yaml"
fi

# Prepare data for DM-VIO
python3 prepare_uzhfpv.py "$SEQ_NAME"

IMG_FOLDER="$SEQ_PATH/img_sequence"
if [ ! -d "$IMG_FOLDER" ]; then
    if [ -d "$SEQ_PATH/img0" ]; then
        IMG_FOLDER="$SEQ_PATH/img0"
    elif [ -d "$SEQ_PATH/img_0" ]; then
        IMG_FOLDER="$SEQ_PATH/img_0"
    elif [ -d "$SEQ_PATH/img" ]; then
        IMG_FOLDER="$SEQ_PATH/img"
    fi
fi

echo "Running dmvio_dataset on $SEQ_NAME with $CALIB and $IMU_CALIB"
echo "output dir $OUT_DIR"
build/bin/dmvio_dataset \
    files="$IMG_FOLDER" \
    tsFile="$SEQ_PATH/times_dmvio.txt" \
    imuFile="$SEQ_PATH/imu_interpolated_dmvio.txt" \
    calib="$CALIB" \
    imuCalib="$IMU_CALIB" \
    settingsFile=configs/uzhfpv/config.yaml \
    mode=1 \
    preset=1 \
    nogui=0 \
    useimu=1 \
    resultsPrefix="$OUT_DIR/"
