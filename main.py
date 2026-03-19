# =====================================================================
# MAIN.PY - THE FLUOROLOCK CONTROL DASHBOARD
# =====================================================================
import os
import re
import simulator
import evaluator

# --- 1. EXECUTION MODE ---
# Options: "simulate_only", "evaluate_only", "run_both"
EXECUTION_MODE = "run_both"  

# If evaluating, specify the run folder. "latest" auto-grabs the most recent run.
TARGET_RUN_FOLDER = "latest"  

# --- 2. FREQUENTLY CHANGED PARAMETERS ---
DATA_ROOT = "data"
PARTICLE_MODE = "100nm"       
TARGET_FND_COUNTS = [0, 1, 5, 10, 20, 50, 100, 200, 500] 
NUM_REPLICATES = 7            

# Hardware Matrix (The parameters to Sweep)
EXPOSURE_CHECKPOINTS = [0.1, 0.25, 0.50, 1.0, 2.0]
CYCLE_CHECKPOINTS = [1, 5, 10, 20, 40, 60, 80, 100] 

# Computing Power

SIZE_X = 960
SIZE_Y = 720
MAX_PARALLEL_WORKERS = 15     

# =====================================================================
# ROUTING UTILITY
# =====================================================================
def get_run_directory(base_dir, particle_mode, is_generating=True, target_run="latest"):
    os.makedirs(base_dir, exist_ok=True)
    existing_runs = []
    pattern = re.compile(rf"^{particle_mode}_run(\d+)$")
    for d in os.listdir(base_dir):
        if os.path.isdir(os.path.join(base_dir, d)):
            match = pattern.match(d)
            if match: existing_runs.append(int(match.group(1)))
    
    if is_generating:
        next_run = max(existing_runs) + 1 if existing_runs else 1
        run_dir = os.path.join(base_dir, f"{particle_mode}_run{next_run}")
        os.makedirs(run_dir, exist_ok=True)
        return run_dir
    else:
        if target_run == "latest":
            if not existing_runs: raise FileNotFoundError(f"❌ No runs found for {particle_mode}.")
            latest_run = max(existing_runs)
            return os.path.join(base_dir, f"{particle_mode}_run{latest_run}")
        else:
            return os.path.join(base_dir, target_run)

# =====================================================================
# SYSTEM DISPATCHER
# =====================================================================
if __name__ == "__main__":
    
    run_directory = None

    if EXECUTION_MODE in ["simulate_only", "run_both"]:
        run_directory = get_run_directory(DATA_ROOT, PARTICLE_MODE, is_generating=True)
        print(f"📂 Activating NEW Unified Data Folder: {run_directory}")
        
        simulator.run_sweep(
            run_dir=run_directory,
            exposure_checkpoints=EXPOSURE_CHECKPOINTS,
            cycle_checkpoints=CYCLE_CHECKPOINTS,
            target_counts=TARGET_FND_COUNTS,
            num_replicates=NUM_REPLICATES,
            size_x=SIZE_X,
            size_y=SIZE_Y,
            particle_mode=PARTICLE_MODE,
            max_workers=MAX_PARALLEL_WORKERS
        )

    if EXECUTION_MODE in ["evaluate_only", "run_both"]:
        if EXECUTION_MODE == "evaluate_only":
            run_directory = get_run_directory(DATA_ROOT, PARTICLE_MODE, is_generating=False, target_run=TARGET_RUN_FOLDER)
            print(f"📂 Routing Evaluation to EXISTING Unified Folder: {run_directory}")
            
        evaluator.run_evaluation(
            run_dir=run_directory,
            exposure_checkpoints=EXPOSURE_CHECKPOINTS,
            cycle_checkpoints=CYCLE_CHECKPOINTS,
            target_counts=TARGET_FND_COUNTS,
            num_replicates=NUM_REPLICATES,
            max_workers=MAX_PARALLEL_WORKERS
        )