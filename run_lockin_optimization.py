import os
import time
import numpy as np
from PIL import Image
from scipy.ndimage import shift
from skimage import filters
from skimage.registration import phase_cross_correlation
from scipy.optimize import curve_fit

import matplotlib
matplotlib.use('TkAgg') 
import matplotlib.pyplot as plt
import config  # Imports your master dashboard settings

# =====================================================================
# OPTIMIZATION DASHBOARD
# =====================================================================
CYCLE_CHECKPOINTS = [1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50] 

# ✅ DYNAMICALLY LINKED TO CONFIG
MAX_VALID_LOD = float(max(config.TARGET_FND_COUNTS))

# =====================================================================
# THE EVALUATOR ENGINE (LOCK-IN ONLY)
# =====================================================================
class LockInEvaluator:
    def __init__(self):
        self.reference_img = None

    def _load_image(self, img_path):
        img_arr = np.array(Image.open(img_path))
        if img_arr.ndim == 3: return img_arr[:, :, 0].astype(float)
        return img_arr.astype(float)

    def extract_lockin_signal_for_n_cycles(self, conc_path, n_cycles):
        """Processes 'n' frames exclusively using the Lock-In math."""
        on_dir = os.path.join(conc_path, "ON")
        off_dir = os.path.join(conc_path, "OFF")
        on_files = sorted([os.path.join(on_dir, f) for f in os.listdir(on_dir)])
        off_files = sorted([os.path.join(off_dir, f) for f in os.listdir(off_dir)])
        
        actual_n = min(n_cycles, len(on_files), len(off_files))
        if actual_n == 0: return 0.0

        self.reference_img = self._load_image(off_files[0])
        off_sum = np.zeros_like(self.reference_img, dtype=float)
        on_sum = np.zeros_like(self.reference_img, dtype=float)

        for i in range(actual_n):
            off_img = self._load_image(off_files[i])
            on_img = self._load_image(on_files[i])
            
            s, _, _ = phase_cross_correlation(self.reference_img, off_img, upsample_factor=10)
            if np.max(np.abs(s)) > 15.0: s = [0.0, 0.0]
                
            off_sum += shift(off_img, shift=s, mode='nearest')
            on_sum += shift(on_img, shift=s, mode='nearest')

        mean_off = off_sum / actual_n
        mean_on = on_sum / actual_n

        # --- Digital Lock-In Amplifier Math ---
        lockin_map = mean_off - mean_on
        sm = filters.gaussian(lockin_map, sigma=1.0, preserve_range=True)
        med = np.median(sm)
        mad = np.median(np.abs(sm - med)) * 1.4826
        if mad == 0: mad = np.std(sm)
        
        pixels = sm[sm > med + (5.0 * mad)]
        return np.sum(pixels) if len(pixels) > 0 else 0.0

# =====================================================================
# 4PL FITTING & VALIDATION MODULE
# =====================================================================
def four_pl_model(x, A, B, C, D):
    return D + (A - D) / (1.0 + (x / C)**B)

def calculate_validated_lod(x_data, y_data, y_err, blank_mean, blank_sd):
    lod_y_thresh = blank_mean + (3.0 * blank_sd)
    mask = x_data > 0
    x_fit, y_fit, err_fit = x_data[mask], y_data[mask], y_err[mask]

    if len(y_fit) == 0:
        return np.nan, 0.0, "Empty Data Array"

    if np.max(y_fit) < (max(blank_mean, 1e-6) * config.MIN_SIGNAL_RISE):
        return np.nan, 0.0, "Signal is flat (No Dose-Response)"

    try:
        guess = [np.min(y_fit), 1.0, np.median(x_fit), np.max(y_fit)]
        # Weighted fit using the true error bars!
        popt, _ = curve_fit(four_pl_model, x_fit, y_fit, p0=guess, 
                            sigma=(err_fit + 1e-8), absolute_sigma=False, maxfev=10000)
        A, B, C, D = popt

        if D <= A: return np.nan, 0.0, "Inverted Curve (D <= A)"

        y_pred = four_pl_model(x_fit, *popt)
        r2 = 1.0 - (np.sum((y_fit - y_pred)**2) / (np.sum((y_fit - np.mean(y_fit))**2) + 1e-12))

        safe_y_thresh = max(lod_y_thresh, A + 1e-6) 
        
        if safe_y_thresh < D:
            val = ((A - D) / (safe_y_thresh - D)) - 1.0
            if val <= 0: return np.nan, r2, "Math Error (Negative root)"
            lod_x = C * (val**(1.0 / B))
            
            if lod_x > MAX_VALID_LOD:
                return np.nan, r2, f"LOD out of bounds (> {MAX_VALID_LOD} FNDs)"
            if lod_x < 0:
                return np.nan, r2, "Negative LOD calculated"
                
            return lod_x, r2, "Valid"
        else:
            return np.nan, r2, "LOD Y-Threshold is higher than curve maximum"
    except Exception as e:
        return np.nan, 0.0, f"Curve Fit Failed"

# =====================================================================
# MAIN EXECUTION
# =====================================================================
if __name__ == "__main__":
    if not os.path.exists(config.DATA_ROOT):
        print(f"❌ Error: Directory '{config.DATA_ROOT}' not found.")
        exit()
        
    sample_rep_dir = os.path.join(config.DATA_ROOT, "Rep_1")
    if not os.path.exists(sample_rep_dir):
        print(f"❌ Error: Replicate folder not found. Run the simulator first!")
        exit()

    conc_map = {}
    for f in os.listdir(sample_rep_dir):
        if f.endswith("_FNDs"):
            try: conc_map[float(f.replace("_FNDs", ""))] = f
            except ValueError: pass
                
    sorted_concs = np.array(sorted(conc_map.keys()))
    evaluator = LockInEvaluator()
    
    # Store final optimization data
    opt_x_cycles = []
    opt_y_lods = []

    print(f"\n🚀 Starting Lock-In Optimization ({config.NUM_REPLICATES} Replicates)...\n")

    for n in CYCLE_CHECKPOINTS:
        print(f"--- 🔄 INTEGRATING {n} CYCLES ---")
        
        # 1. Gather raw fluxes across all replicates for this cycle count
        raw_fluxes = {conc: [] for conc in sorted_concs}
        for rep in range(1, config.NUM_REPLICATES + 1):
            rep_dir = os.path.join(config.DATA_ROOT, f"Rep_{rep}")
            for conc in sorted_concs:
                f_lock = evaluator.extract_lockin_signal_for_n_cycles(os.path.join(rep_dir, conc_map[conc]), n)
                raw_fluxes[conc].append(f_lock)

        # 2. Calculate true means and standard deviations
        mean_fluxes = []
        std_fluxes = []
        blank_mean = 0.0
        blank_sd = 0.0

        for conc in sorted_concs:
            f_arr = np.array(raw_fluxes[conc])
            m, s = np.mean(f_arr), np.std(f_arr)
            mean_fluxes.append(m)
            std_fluxes.append(s)
            
            if conc == 0.0:
                blank_mean = m
                blank_sd = max(s, 1e-6) # Protect against perfect zero SD

        mean_fluxes = np.array(mean_fluxes)
        std_fluxes = np.array(std_fluxes)

        # 3. Calculate Validated LOD for this Cycle Count
        lod, r2, status = calculate_validated_lod(sorted_concs, mean_fluxes, std_fluxes, blank_mean, blank_sd)
        
        if not np.isnan(lod):
            opt_x_cycles.append(n)
            opt_y_lods.append(lod)
            print(f"  ✅ Lock-In LOD = {lod:.1f} FNDs (R^2 = {r2:.3f})")
        else:
            print(f"  ❌ Rejected -> {status}")
        print("")

    # ==========================================
    # FINAL PLOTTING: LOD vs TIME
    # ==========================================
    plt.figure(figsize=(10, 6))
    fig = plt.gcf()
    fig.canvas.manager.set_window_title('Lock-In Optimization')

    if len(opt_x_cycles) > 0:
        # 1. Clean line plot
        plt.plot(opt_x_cycles, opt_y_lods, '-o', color='#2ca02c', markersize=8, linewidth=2.5, label='Lock-In Limit of Detection')
        
        # 2. Find the Absolute Best LOD
        best_lod_idx = np.argmin(opt_y_lods)
        best_x = opt_x_cycles[best_lod_idx]
        best_y = opt_y_lods[best_lod_idx]
        
        # 3. Mark the Optimal Point with a Golden Star
        plt.plot(best_x, best_y, marker='*', color='gold', ms=20, mec='black', zorder=10, label="Optimal LOD")
        
        # 4. Draw a dotted line down to the x-axis for visual emphasis
        plt.axvline(x=best_x, color='purple', linestyle=':', linewidth=2, zorder=5)

        # 5. Add the floating text box annotation
        plt.annotate(f"Optimal Efficiency:\n{best_y:.1f} FNDs @ {best_x} Cycles", 
                     (best_x, best_y),
                     textcoords="offset points", xytext=(15, 10), ha='left',
                     fontsize=11, fontweight='bold', color='black',
                     bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="purple", lw=1.5),
                     zorder=15)
                     
        plt.legend(fontsize=12, loc='upper right')
    else:
        plt.text(0.5, 0.5, "Optimization failed: No valid LODs found.", 
                 ha='center', va='center', transform=plt.gca().transAxes, fontsize=12, color='red', fontweight='bold')

    plt.title("Assay Optimization: Sensitivity vs. Microwave Integration Cycles", fontsize=14, fontweight='bold')
    plt.xlabel("Integration Time (Number of Microwave Cycles)", fontsize=12, fontweight='bold')
    plt.ylabel("Validated Limit of Detection (FNDs/FOV)", fontsize=12, fontweight='bold')
    
    plt.yscale('log')
    min_lod_plot = min(opt_y_lods) if len(opt_y_lods) > 0 else 0.5 
    plt.ylim(min_lod_plot * 0.5, MAX_VALID_LOD * 1.5)
    plt.xticks(CYCLE_CHECKPOINTS)
    
    plt.grid(True, which='major', linestyle='-', linewidth=0.8, alpha=0.7)
    plt.grid(True, which='minor', linestyle=':', linewidth=0.4, alpha=0.5)
    
    plt.tight_layout()
    plt.savefig("LockIn_Optimization_Curve.png", dpi=300)
    print("📸 Saved plot to: LockIn_Optimization_Curve.png")
    
    plt.show()
