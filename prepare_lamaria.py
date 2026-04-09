import os
import sys
import subprocess
import argparse
import csv
from pathlib import Path

def prepare_sequence(seq_path):
    seq_path = Path(seq_path)
    if not seq_path.is_dir():
        return

    seq_name = seq_path.name
    print(f"Preparing sequence: {seq_name}")

    #aria_path = seq_path / "asl_folder" / seq_name / "aria"
    # Actually, let's try to find it more robustly or follow the user's path
    # data/lamaria/training/R_01_easy/asl_folder/R_01_easy/aria/cam0/data/1389350666375.png
    
    aria_path = seq_path / "asl_folder" / seq_name / "aria"
    if not aria_path.exists():
        # Maybe it's not nested under asl_folder/seq_name?
        # Let's search for 'aria' folder under seq_path
        paths = list(seq_path.glob("**/aria"))
        if paths:
            aria_path = paths[0]
        else:
            print(f"  Error: Could not find 'aria' directory under {seq_path}")
            return

    cam0_dir = aria_path / "cam0" / "data"
    imu_csv = aria_path / "imu0" / "data.csv"
    
    if not cam0_dir.exists():
        print(f"  Error: Camera directory not found: {cam0_dir}")
        return
    if not imu_csv.exists():
        print(f"  Error: IMU data.csv not found: {imu_csv}")
        return

    # Create img0 symlink in seq_path if it doesn't exist
    img0_link = seq_path / "img0"
    if not img0_link.exists():
        print(f"  Creating symlink img0 -> {cam0_dir}")
        # Use relative path for symlink
        os.symlink(os.path.relpath(cam0_dir, seq_path), img0_link)

    # 1. times_dmvio.txt
    times_dmvio = seq_path / "times_dmvio.txt"
    print(f"  Creating/Updating times_dmvio.txt")
    # Get all PNG files, sort them alphabetically
    img_files = sorted(list(cam0_dir.glob("*.png")))
    if not img_files:
        print(f"  Warning: No PNG images found in {cam0_dir}")
    else:
        try:
            with open(times_dmvio, 'w') as f_out:
                for img_pth in img_files:
                    ts_str = img_pth.stem # filename without .png
                    try:
                        ts_ns = int(ts_str)
                        ts_sec = ts_ns / 1e9
                        f_out.write(f"{ts_ns} {ts_sec}\n")
                    except ValueError:
                        continue
        except Exception as e:
            print(f"  Error creating times_dmvio.txt: {e}")

    # 2. imu_dmvio.txt
    imu_dmvio = seq_path / "imu_dmvio.txt"
    print(f"  Creating/Updating imu_dmvio.txt")
    try:
        with open(imu_csv, 'r') as f_in, open(imu_dmvio, 'w') as f_out:
            reader = csv.reader(f_in)
            for row in reader:
                if not row or row[0].startswith('#'): continue
                if len(row) >= 7:
                    try:
                        # row[0] is timestamp_ns
                        ts_ns = int(row[0])
                        line = f"{ts_ns} {' '.join(row[1:7])}\n"
                        f_out.write(line)
                    except ValueError:
                        continue
    except Exception as e:
        print(f"  Error creating imu_dmvio.txt: {e}")

    # 3. Interpolate IMU
    imu_interp = seq_path / "imu_interpolated_dmvio.txt"
    if imu_dmvio.exists() and times_dmvio.exists():
        print(f"  Interpolating IMU -> {imu_interp.name}")
        # The script is in dm-vio-python-tools/interpolate_imu_file.py
        script_path = Path(__file__).parent / "dm-vio-python-tools" / "interpolate_imu_file.py"
        if not script_path.exists():
            script_path = Path("dm-vio-python-tools/interpolate_imu_file.py")
        
        if script_path.exists():
            cmd = [
                "pixi", "run", "python3", str(script_path),
                "--input", str(imu_dmvio),
                "--times", str(times_dmvio),
                "--output", str(imu_interp),
                "--times-column", "0"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  Error interpolating IMU: {result.stderr}")
        else:
            print(f"  Error: Could not find dm-vio-python-tools/interpolate_imu_file.py")

def main():
    parser = argparse.ArgumentParser(description="Prepare Lamaria data for DM-VIO.")
    parser.add_argument("sequence", nargs="?", help="Specific sequence name (e.g., R_01_easy). If omitted, processes all in data/lamaria/training")
    parser.add_argument("--data_dir", default="data/lamaria/training", help="Root directory for sequences")

    args = parser.parse_args()

    if args.sequence:
        seq_path = Path(args.data_dir) / args.sequence
        if not seq_path.exists():
             seq_path = Path(args.sequence) # Maybe it's an absolute path?
        
        if seq_path.is_dir():
             prepare_sequence(seq_path)
        else:
             print(f"Error: {seq_path} is not a directory.")
    else:
        root = Path(args.data_dir)
        if not root.is_dir():
            print(f"Error: {root} not found.")
            sys.exit(1)
        
        for p in sorted(root.glob("*")):
            if p.is_dir():
                prepare_sequence(p)

if __name__ == "__main__":
    main()
