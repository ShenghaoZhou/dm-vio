#!/bin/bash

# Configuration
CONFIG="configs/lamaria/config.yaml"
DATA_DIR="data/lamaria/training"
RESULTS_DIR="results/lamaria"

# Create results directory
mkdir -p "$RESULTS_DIR"

# List of sequences
SEQUENCES=(
# "R_01_easy"
"R_02_easy"
"R_03_easy"
"R_04_medium"
"R_05_medium"
"R_06_medium"
"R_07_medium"
"R_08_hard"
"R_09_hard"
"R_10_hard"
)

for SEQ in "${SEQUENCES[@]}"; do
    echo "========================================================="
    echo "Running sequence: $SEQ"
    echo "========================================================="
    
    # Prepare paths
    SEQ_PATH="$DATA_DIR/$SEQ"
    IMG_DIR="$SEQ_PATH/img0"
    IMU_FILE="$SEQ_PATH/imu_interpolated_dmvio.txt"
    TS_FILE="$SEQ_PATH/times_dmvio.txt"
    JSON_CALIB="$SEQ_PATH/pinhole_calibrations/$SEQ.json"
    SEQ_RESULTS="$RESULTS_DIR/$SEQ/"
    
    # Create sequence results directory
    mkdir -p "$SEQ_RESULTS"

    # Extract intrinsics and generate camchain.yaml using helper script
    # Use pixi run to ensure pyquaternion and other dependencies are available
    TEMP_CAMCHAIN="$SEQ_RESULTS/camchain_dmvio.yaml"
    pixi run python3 generate_camchain_yaml.py "$JSON_CALIB" "$TEMP_CAMCHAIN"
    
    # Extract intrinsics using Python for cam_dmvio.txt
    PYTHON_CMD="import json; data=json.load(open('$JSON_CALIB')); c0=data['cam0']; p=c0['params']; r=c0['resolution']; print(f'{p[0]} {p[1]} {p[2]} {p[3]} {r[\"width\"]} {r[\"height\"]}')"
    read FX FY CX CY W H <<< $(python3 -c "$PYTHON_CMD")
    
    # Adjust output resolution to be divisible by 16
    W_OUT=$(( (W / 16) * 16 ))
    H_OUT=$(( (H / 16) * 16 ))
    
    # Create temporary calibration file
    TEMP_CALIB="$SEQ_RESULTS/cam_dmvio.txt"
    echo "Pinhole $FX $FY $CX $CY 0" > "$TEMP_CALIB"
    echo "$W $H" >> "$TEMP_CALIB"
    echo "crop" >> "$TEMP_CALIB"
    echo "$W_OUT $H_OUT" >> "$TEMP_CALIB"

    # Prepare data for DM-VIO
    python3 prepare_lamaria.py "$SEQ" --data_dir "$DATA_DIR"

    IMG_DIR="$SEQ_PATH/img_sequence"
    if [ ! -d "$IMG_DIR" ]; then
        if [ -d "$SEQ_PATH/img0" ]; then
            IMG_DIR="$SEQ_PATH/img0"
        elif [ -d "$SEQ_PATH/img_0" ]; then
            IMG_DIR="$SEQ_PATH/img_0"
        elif [ -d "$SEQ_PATH/img" ]; then
            IMG_DIR="$SEQ_PATH/img"
        fi
    fi

    echo "Running dmvio_dataset on $SEQ with $FX $FY $CX $CY $W $H"
    echo "Results saved to: $SEQ_RESULTS"
    
    pixi run ./build/bin/dmvio_dataset \
        files="$IMG_DIR" \
        imuFile="$IMU_FILE" \
        tsFile="$TS_FILE" \
        calib="$TEMP_CALIB" \
        settingsFile="$CONFIG" \
        imuCalib="$TEMP_CAMCHAIN" \
        resultsPrefix="$SEQ_RESULTS" \
        nogui=1 \
        preset=1 \
        mode=1
        
    echo "Finished $SEQ. Results saved to $SEQ_RESULTS"
done
