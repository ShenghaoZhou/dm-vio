import os
import glob
import subprocess
from pathlib import Path

def unzip_all():
    base_dir = Path("data/lamaria/training")
    
    # Find all zip files matching the pattern
    zip_files = list(base_dir.glob("R_*/asl_folder/*.zip"))
    
    if not zip_files:
        print("No zip files found matching data/lamaria/training/R_*/asl_folder/*.zip")
        return

    print(f"Found {len(zip_files)} zip files to extract.")

    for zip_path in zip_files:
        target_dir = zip_path.parent
        print(f"\nUnzipping {zip_path.name} into {target_dir}...")
        
        # Using subprocess to call the system 'unzip' command which is usually faster
        # -o: overwrite existing files without prompting
        # -q: quiet mode
        # -d: extract files into exdir
        cmd = ["unzip", "-o", "-q", str(zip_path), "-d", str(target_dir)]
        
        try:
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(f"Successfully unzipped {zip_path.name}")
        except subprocess.CalledProcessError as e:
            print(f"Error unzipping {zip_path.name}:")
            print(e.stderr.decode('utf-8'))

if __name__ == "__main__":
    unzip_all()
