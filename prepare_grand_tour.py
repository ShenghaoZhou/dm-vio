import os
import sys
import subprocess
import argparse
import tarfile
from pathlib import Path

try:
    import zarr
    import numpy as np
    from ruamel.yaml import YAML
    from pyquaternion import Quaternion
except ImportError:
    print("Warning: zarr, numpy, ruamel.yaml, or pyquaternion not found. Some preparation steps will be skipped.")
    zarr = None
    np = None
    YAML = None
    Quaternion = None

def generate_dmvio_configs(seq_path):
    if not (np and YAML and Quaternion):
        return
    seq_path = Path(seq_path)
    metadata_dir = seq_path / "metadata"
    
    caminfo_path = metadata_dir / "alphasense_front_left_caminfo.yaml"
    cam_ext_path = metadata_dir / "alphasense_front_left.yaml"
    imu_ext_path = metadata_dir / "alphasense_imu.yaml"
    
    if not (caminfo_path.exists() and cam_ext_path.exists() and imu_ext_path.exists()):
        # Try finding in seq_path directly if not in metadata subfolder
        if not metadata_dir.exists():
            metadata_dir = seq_path
            caminfo_path = metadata_dir / "alphasense_front_left_caminfo.yaml"
            cam_ext_path = metadata_dir / "alphasense_front_left.yaml"
            imu_ext_path = metadata_dir / "alphasense_imu.yaml"
            if not caminfo_path.exists(): return

    print(f"  Generating DM-VIO configs from metadata...")
    
    try:
        yaml_loader = YAML()
        with open(caminfo_path, 'r') as f:
            caminfo_full = yaml_loader.load(f)
            caminfo = caminfo_full['camera_info'] if 'camera_info' in caminfo_full else caminfo_full
        
        with open(cam_ext_path, 'r') as f:
            cam_ext_full = yaml_loader.load(f)
            cam_ext = cam_ext_full['transform'] if 'transform' in cam_ext_full else cam_ext_full
            
        with open(imu_ext_path, 'r') as f:
            imu_ext_full = yaml_loader.load(f)
            imu_ext = imu_ext_full['transform'] if 'transform' in imu_ext_full else imu_ext_full
            
        # Intrinsics
        K = caminfo['K']
        D = caminfo['D']
        width = caminfo['width']
        height = caminfo['height']
        model = caminfo.get('distortion_model', 'equidistant').lower()
        
        fx, fy, cx, cy = float(K[0]), float(K[4]), float(K[2]), float(K[5])
        
        # Write camera.txt
        cam_txt_path = seq_path / "camera.txt"
        with open(cam_txt_path, 'w') as f:
            if 'equidistant' in model:
                d = [float(x) for x in D]
                f.write(f"EquiDistant {fx:.6f} {fy:.6f} {cx:.6f} {cy:.6f} {d[0]:.6f} {d[1]:.6f} {d[2]:.6f} {d[3]:.6f}\n")
            elif 'plumb' in model or 'radtan' in model:
                d = [float(x) for x in D]
                f.write(f"RadTan {fx:.6f} {fy:.6f} {cx:.6f} {cy:.6f} {d[0]:.6f} {d[1]:.6f} {d[2]:.6f} {d[3]:.6f}\n")
            else:
                f.write(f"Pinhole {fx:.6f} {fy:.6f} {cx:.6f} {cy:.6f} 0.0\n")
            
            f.write(f"{int(width)} {int(height)}\n")
            f.write("crop\n")
            w_crop = (int(width) // 32) * 32
            h_crop = (int(height) // 32) * 32
            f.write(f"{w_crop} {h_crop}\n")
            
        # Extrinsics
        def get_T(trans):
            rot = trans['rotation']
            t = trans['translation']
            q = Quaternion(rot['w'], rot['x'], rot['y'], rot['z'])
            T = np.eye(4)
            T[:3, :3] = q.rotation_matrix
            T[0, 3] = t['x']; T[1, 3] = t['y']; T[2, 3] = t['z']
            return T
            
        T_base_cam = get_T(cam_ext)
        T_base_imu = get_T(imu_ext)
        
        # T_cam_imu here means T_imu_cam (Camera to IMU) based on user's correction
        T_cam_imu = np.linalg.inv(T_base_imu) @ T_base_cam
        
        camchain_path = seq_path / "camchain.yaml"
        camchain_data = {
            'cam0': {
                'T_cam_imu': T_cam_imu.tolist(),
                'camera_model': 'pinhole',
                'intrinsics': [float(fx), float(fy), float(cx), float(cy)],
                'resolution': [int(width), int(height)]
            }
        }
        with open(camchain_path, 'w') as f:
            yaml_loader.dump(camchain_data, f)
            
        print(f"    Created camera.txt and camchain.yaml for {seq_path.name}")
        print(f"    K: fx={fx:.2f}, cx={cx:.2f}, cy={cy:.2f}, model={model}")
        
    except Exception as e:
        print(f"    Error generating configs: {e}")


def extract_zarr_data(seq_path):
    # Find IMU and Camera tar files
    imu_tar = seq_path / "data" / "alphasense_imu.tar"
    cam_tar = seq_path / "data" / "alphasense_front_left.tar"
    
    # Target directories for extracted zarr
    imu_zarr_dir = seq_path / "data" / "alphasense_imu"
    cam_zarr_dir = seq_path / "data" / "alphasense_front_left"

    # Extract IMU if needed
    if not imu_zarr_dir.exists() and imu_tar.exists():
        print(f"  Extracting {imu_tar.name} ...")
        try:
             with tarfile.open(imu_tar) as tar:
                 tar.extractall(path=seq_path / "data")
        except Exception as e:
             print(f"  Error extracting IMU tar: {e}")

    # Extract Camera if needed
    if not cam_zarr_dir.exists() and cam_tar.exists():
        print(f"  Extracting {cam_tar.name} ...")
        try:
             with tarfile.open(cam_tar) as tar:
                 tar.extractall(path=seq_path / "data")
        except Exception as e:
             print(f"  Error extracting camera tar: {e}")

    if not zarr:
         print("  Cannot open zarr data: zarr library missing.")
         return
    
    # Process IMU
    if imu_zarr_dir.exists():
        print(f"  Reading IMU zarr data from {imu_zarr_dir.name}")
        try:
            group = zarr.open_group(str(imu_zarr_dir), mode='r')
            if 'timestamp' not in group:
                 inner = imu_zarr_dir / "alphasense_imu"
                 if inner.exists(): group = zarr.open_group(str(inner), mode='r')
            
            if 'timestamp' in group:
                timestamps = group['timestamp'][:] 
                ang_vel = group['ang_vel'][:]
                lin_acc = group['lin_acc'][:]
                imu_dmvio = seq_path / "imu_dmvio.txt"
                print(f"  Creating imu_dmvio.txt from zarr ({len(timestamps)} samples)")
                with open(imu_dmvio, 'w') as f_out:
                    for i in range(len(timestamps)):
                        t_val = timestamps[i]
                        t_ns = int(round(t_val * 1e9)) if t_val < 1e11 else int(t_val)
                        w = ang_vel[i]
                        a = lin_acc[i]
                        f_out.write(f"{t_ns} {w[0]} {w[1]} {w[2]} {a[0]} {a[1]} {a[2]}\n")
        except Exception as e:
            print(f"  Error reading IMU zarr: {e}")

    # Process Camera
    if cam_zarr_dir.exists():
        print(f"  Reading camera zarr data from {cam_zarr_dir.name}")
        try:
            group = zarr.open_group(str(cam_zarr_dir), mode='r')
            if 'timestamp' not in group:
                 inner = cam_zarr_dir / "alphasense_front_left"
                 if inner.exists(): group = zarr.open_group(str(inner), mode='r')
            
            if 'timestamp' in group:
                timestamps = group['timestamp'][:]
                times_dmvio = seq_path / "times_dmvio.txt"
                print(f"  Creating times_dmvio.txt from camera zarr ({len(timestamps)} samples)")
                with open(times_dmvio, 'w') as f_out:
                    for i in range(len(timestamps)):
                        t_val = timestamps[i]
                        t_ns = int(round(t_val * 1e9)) if t_val < 1e11 else int(t_val)
                        t_sec = t_ns / 1e9
                        f_out.write(f"{t_ns} {t_sec}\n")
        except Exception as e:
            print(f"  Error reading camera zarr: {e}")

def prepare_sequence(seq_path):
    seq_path = Path(seq_path)
    if not seq_path.is_dir():
        return

    seq_name = seq_path.name
    print(f"Preparing sequence: {seq_name}")

    # 0. Generate DM-VIO configs from metadata
    generate_dmvio_configs(seq_path)

    # 1. Ensure images are extracted
    img_tar = seq_path / "images" / "alphasense_front_left.tar"
    img_dir = seq_path / "images" / "alphasense_front_left"
    if img_tar.exists() and not img_dir.exists():
        print(f"  Extracting {img_tar.name} ...")
        try:
             img_dir.mkdir(parents=True, exist_ok=True)
             with tarfile.open(img_tar) as tar:
                 tar.extractall(path=img_dir.parent)
        except Exception as e:
             print(f"  Error extracting image tar: {e}")

    # 2. Extract and process Zarr data (Always the source of truth for timestamps)
    extract_zarr_data(seq_path)
    
    times_dmvio = seq_path / "times_dmvio.txt"
    imu_dmvio = seq_path / "imu_dmvio.txt"
    
    if not times_dmvio.exists():
        print(f"  ERROR: Image timestamps not found in {seq_path}. Ensure camera zarr is available.")
        return

    if not imu_dmvio.exists():
        print(f"  ERROR: IMU data not found in {seq_path}. Ensure IMU zarr is available.")
        return

    # 3. img0 directory with padded symlinks
    # Grand Tour images are in images/alphasense_front_left/
    img_dir = seq_path / "images" / "alphasense_front_left"
    img0_dir = seq_path / "img0"
    
    if img_dir.exists():
        if not img0_dir.exists():
             print(f"  Creating padded image folder img0")
             img0_dir.mkdir(parents=True, exist_ok=True)
        
        # Grand Tour images are already padded (000000.jpeg)
        # But we create symlinks in img0 for consistency with other datasets.
        img_files = sorted(list(img_dir.glob("*.jpeg")) + list(img_dir.glob("*.jpg")))
        print(f"  Found {len(img_files)} images in {img_dir.name}")
        for f in img_files:
            basename = f.name
            try:
                # Filenames are like 000000.jpeg
                # We can just keep them or ensure they are padded.
                num_part = "".join(filter(str.isdigit, basename))
                if not num_part: continue
                num = int(num_part)
                padded_num = f"{num:06d}"
                ext = f.suffix
                new_fn = f"image_0_{padded_num}{ext}"
                dst = img0_dir / new_fn
                
                if not os.path.lexists(dst):
                    # Relativize the source path
                    src_rel = os.path.relpath(f, img0_dir)
                    os.symlink(src_rel, dst)
            except Exception as e:
                # print(f"    Error symlinking {basename}: {e}")
                pass

    # 4. Interpolate IMU
    imu_interp = seq_path / "imu_interpolated_dmvio.txt"
    if imu_dmvio.exists() and times_dmvio.exists():
        print(f"  Interpolating IMU -> {imu_interp.name}")
        # Find interpolation script
        script_path = Path("dm-vio-python-tools/interpolate_imu_file.py")
        if not script_path.exists():
            # Try to find it relative to current file
            script_path = Path(__file__).parent / "dm-vio-python-tools" / "interpolate_imu_file.py"
            
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
             print(f"  Error: Could not find interpolate_imu_file.py")

def main():
    parser = argparse.ArgumentParser(description="Prepare Grand Tour data for DM-VIO.")
    parser.add_argument("sequence", nargs="?", help="Specific sequence folder (e.g., 2024-10-01-11-29-55). If omitted, processes all in data/grand_tour")
    parser.add_argument("--data_dir", default="data/grand_tour", help="Root directory for sequences")

    args = parser.parse_args()

    if args.sequence:
        seq_path = Path(args.data_dir) / args.sequence
        if not seq_path.exists():
             seq_path = Path(args.sequence) # Try absolute path
        
        if seq_path.is_dir():
            prepare_sequence(seq_path)
        else:
            print(f"Error: {seq_path} is not a directory.")
    else:
        root = Path(args.data_dir)
        if not root.is_dir():
            print(f"Error: {root} not found.")
            sys.exit(1)
        
        # Iterate over all folders that look like dates (sequences)
        for p in sorted(root.glob("*")):
            if p.is_dir() and p.name[0].isdigit():
                prepare_sequence(p)

if __name__ == "__main__":
    main()
