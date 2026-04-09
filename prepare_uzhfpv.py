import os
import sys
import subprocess
import argparse
from pathlib import Path

def prepare_sequence(seq_path):
    seq_path = Path(seq_path)
    if not seq_path.is_dir():
        return

    seq_name = seq_path.name
    print(f"Preparing sequence: {seq_name}")

    # 1. times_dmvio.txt
    times_txt = seq_path / "times.txt"
    times_dmvio = seq_path / "times_dmvio.txt"
    if times_txt.exists():
        print(f"  Creating/Updating times_dmvio.txt")
        try:
            with open(times_txt, 'r') as f_in, open(times_dmvio, 'w') as f_out:
                for line in f_in:
                    if line.startswith('#') or not line.strip(): continue
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            t_sec = float(parts[1])
                            t_ns = int(round(t_sec * 1e9))
                            f_out.write(f"{t_ns} {t_sec}\n")
                        except ValueError:
                            continue
        except Exception as e:
            print(f"  Error creating times_dmvio.txt: {e}")

    # 2. imu_dmvio.txt
    imu_txt = seq_path / "imu.txt"
    imu_dmvio = seq_path / "imu_dmvio.txt"
    if imu_txt.exists():
        print(f"  Creating/Updating imu_dmvio.txt")
        try:
            with open(imu_txt, 'r') as f_in, open(imu_dmvio, 'w') as f_out:
                for line in f_in:
                    if line.startswith('#') or not line.strip(): continue
                    parts = line.split()
                    if len(parts) >= 8:
                        # Original columns: # id timestamp wx wy wz ax ay az
                        # Target: nanoseconds wx wy wz ax ay az
                        try:
                            t_sec = float(parts[1])
                            t_ns = int(round(t_sec * 1e9))
                            f_out.write(f"{t_ns} {' '.join(parts[2:8])}\n")
                        except ValueError:
                            continue
        except Exception as e:
            print(f"  Error creating imu_dmvio.txt: {e}")

    # 3. img0 directory with padded symlinks
    img_dir = seq_path / "img"
    img0_dir = seq_path / "img0"
    if img_dir.exists():
        if not img0_dir.exists():
             print(f"  Creating padded image folder img0")
             img0_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if we need to create symlinks
        img_files = sorted(list(img_dir.glob("*.png")))
        # If the number of files matches, we might skip, but it's safer to check individually
        # especially since we want to handle interrupted runs.
        for f in img_files:
            basename = f.name
            try:
                # Extract original number. Filenames are like image_0_N.png
                num_part = basename.split('_')[-1]
                num_str = "".join(filter(str.isdigit, num_part))
                if not num_str: continue
                num = int(num_str)
                padded_num = f"{num:06d}"
                new_fn = f"image_0_{padded_num}.png"
                dst = img0_dir / new_fn
                
                # Use is_symlink() or lexists() because exists() is false for broken symlinks
                if not dst.exists():
                    os.symlink(f"../img/{basename}", dst)
            except (ValueError, IndexError) as e:
                # print(f"  Warning: skipping {basename} due to {e}")
                pass

    # 4. Interpolate IMU
    imu_interp = seq_path / "imu_interpolated_dmvio.txt"
    if imu_dmvio.exists() and times_dmvio.exists():
        print(f"  Interpolating IMU -> {imu_interp.name}")
        cmd = [
            "pixi", "run", "python3", "dm-vio-python-tools/interpolate_imu_file.py",
            "--input", str(imu_dmvio),
            "--times", str(times_dmvio),
            "--output", str(imu_interp),
            "--times-column", "0"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  Error interpolating IMU: {result.stderr}")

def main():
    parser = argparse.ArgumentParser(description="Prepare UZHFPV data for DM-VIO.")
    parser.add_argument("sequence", nargs="?", help="Specific sequence name (optional). If omitted, processes all in data/uzhfpv")
    parser.add_argument("--data_dir", default="data/uzhfpv", help="Root directory for sequences")

    args = parser.parse_args()

    if args.sequence:
        seq_path = Path(args.data_dir) / args.sequence
        if not seq_path.exists():
             # maybe it's an absolute path
             seq_path = Path(args.sequence)
        prepare_sequence(seq_path)
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
