import os
import subprocess
import glob
from pathlib import Path

def prepare_gt_seconds(raw_gt_path, processed_gt_path):
    """Converts Lamaria ground truth (nanoseconds) to TUM format (seconds)."""
    if not os.path.exists(raw_gt_path):
        return False
    
    try:
        with open(raw_gt_path, 'r') as f_in, open(processed_gt_path, 'w') as f_out:
            for line in f_in:
                if line.startswith('#') or not line.strip():
                    f_out.write(line)
                    continue
                parts = line.split()
                if len(parts) >= 8:
                    try:
                        ts_ns = int(parts[0])
                        ts_sec = ts_ns / 1e9
                        # TUM format: timestamp tx ty tz qx qy qz qw
                        new_line = f"{ts_sec:.9f} {' '.join(parts[1:8])}\n"
                        f_out.write(new_line)
                    except ValueError:
                        continue
        return True
    except Exception as e:
        print(f"Error preparing GT for {raw_gt_path}: {e}")
        return False

def evaluate_all_lamaria():
    data_dir = "data/lamaria/training"
    eval_tool_ate = "dm-vio-python-tools/trajectory_evaluation/evaluate_ate.py"
    eval_tool_rpe = "dm-vio-python-tools/trajectory_evaluation/evaluate_rpe.py"
    
    rpe_deltas = [8, 16, 24, 32, 40, 48]
    
    header = f"{'Sequence':<40} | {'ATE (m)':<8} | {'ATE(deg)':<8} | " + " | ".join([f"RPE{d}m" for d in rpe_deltas])
    print(header)
    print("-" * len(header))
    
    results_list = []
    
    # Sort sequences to process them in order
    sequences = sorted([d for d in glob.glob(os.path.join(data_dir, "*")) if os.path.isdir(d)])
    
    for seq_path in sequences:
        seq_name = os.path.basename(seq_path)
        
        # Lamaria GT is in ground_truth/pGT/<seq_name>.txt with timestamps in nanoseconds
        raw_gt_file = os.path.join(seq_path, "ground_truth/pGT", f"{seq_name}.txt")
        # We create a version with seconds for the evaluation tool
        gt_file = os.path.join(seq_path, "groundtruth_seconds.txt")
        res_file = os.path.join(seq_path, "res/result.txt")
        
        if os.path.exists(raw_gt_file):
            if not os.path.exists(gt_file) or os.path.getmtime(raw_gt_file) > os.path.getmtime(gt_file):
                prepare_gt_seconds(raw_gt_file, gt_file)
        
        if os.path.exists(gt_file) and os.path.exists(res_file):
            if os.path.getsize(res_file) == 0:
                print(f"{seq_name:<40} | Result file is empty")
                continue
                
            try:
                # Need to set PYTHONPATH to include dm-vio-python-tools
                env = os.environ.copy()
                env["PYTHONPATH"] = env.get("PYTHONPATH", "") + ":" + str(Path("dm-vio-python-tools").absolute())
                
                import sys
                
                # Check if result file is valid (not all zeros or corrupted)
                with open(res_file, 'r') as f:
                    first_line = f.readline()
                    if not first_line or first_line.startswith("0 "):
                        print(f"{seq_name:<40} | Not re-processed yet (empty or 0 timestamps)")
                        continue

                # Run ATE
                cmd_ate = [sys.executable, eval_tool_ate, gt_file, res_file, "--verbose"]
                result_ate = subprocess.run(cmd_ate, env=env, capture_output=True, text=True)
                
                if result_ate.returncode != 0:
                     print(f"{seq_name:<40} | ATE Error: {result_ate.stderr.strip()[:50]}")
                     continue

                lines_ate = result_ate.stdout.splitlines()
                ate_rmse = "N/A"
                ate_rot_rmse = "N/A"
                for line in lines_ate:
                    if "absolute_translational_error.rmse" in line:
                        ate_rmse = line.split()[-2]
                    if "absolute_rotational_error.rmse" in line:
                        ate_rot_rmse = line.split()[-2]
                
                # Run RPE for multiple deltas
                rpe_results = []
                for d in rpe_deltas:
                    cmd_rpe = [sys.executable, eval_tool_rpe, gt_file, res_file, "--fixed_delta", "--delta", str(d), "--delta_unit", "m", "--verbose"]
                    result_rpe = subprocess.run(cmd_rpe, env=env, capture_output=True, text=True)
                    
                    if result_rpe.returncode == 0:
                        lines_rpe = result_rpe.stdout.splitlines()
                        rpe_val = "N/A"
                        for line in lines_rpe:
                            if "translational_error.mean" in line:
                                rpe_val = line.split()[-2]
                                break
                        rpe_results.append(rpe_val)
                    else:
                        rpe_results.append("N/A")
                
                rpe_line = " | ".join([f"{val:<6}" for val in rpe_results])
                print(f"{seq_name:<40} | {ate_rmse:<8} | {ate_rot_rmse:<8} | {rpe_line}")
                results_list.append((seq_name, ate_rmse, ate_rot_rmse, rpe_results))
                
            except Exception as e:
                print(f"{seq_name:<40} | Exception: {str(e)}")
        else:
            missing = []
            if not os.path.exists(raw_gt_file) and not os.path.exists(gt_file): missing.append("gt")
            if not os.path.exists(res_file): missing.append("res")
            # print(f"{seq_name:<40} | Missing: {', '.join(missing)}")

if __name__ == "__main__":
    evaluate_all_lamaria()
