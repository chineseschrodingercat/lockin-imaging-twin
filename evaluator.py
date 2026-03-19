# =====================================================================
# EVALUATOR.PY - 4PL ANALYSIS & HEATMAP GENERATION
# =====================================================================
import os
import time
import numpy as np
import pandas as pd
import concurrent.futures
from scipy.optimize import curve_fit
import matplotlib
matplotlib.use('TkAgg') 
import matplotlib.pyplot as plt
import seaborn as sns 
from tqdm import tqdm

import config
from methods import evaluate_fov_worker

def four_pl_model(x, A, B, C, D):
    return D + (A - D) / (1.0 + (x / C)**B)

def calculate_validated_lod(x_data, y_data, y_err, blank_mean, blank_sd, max_valid_lod):
    lod_y_thresh = blank_mean + (3.0 * blank_sd)
    mask = x_data > 0
    x_fit, y_fit, err_fit = x_data[mask], y_data[mask], y_err[mask]

    if len(y_fit) == 0 or np.max(y_fit) < (max(blank_mean, 1e-6) * config.MIN_SIGNAL_RISE): 
        return np.nan, 0.0

    try:
        guess = [max(0, np.min(y_fit)), 1.0, np.median(x_fit), np.max(y_fit)]
        bounds = ([0, 0, 0, 0], [np.inf, 10.0, np.inf, np.inf])
        popt, _ = curve_fit(four_pl_model, x_fit, y_fit, p0=guess, bounds=bounds,
                            sigma=(err_fit + 1e-8), absolute_sigma=False, maxfev=10000)
        A, B, C, D = popt

        if D <= A: return np.nan, 0.0
        
        y_pred = four_pl_model(x_fit, *popt)
        r2 = 1.0 - (np.sum((y_fit - y_pred)**2) / (np.sum((y_fit - np.mean(y_fit))**2) + 1e-12))

        if r2 < config.MIN_R_SQUARED: return np.nan, r2

        safe_y_thresh = max(lod_y_thresh, A + 1e-6) 
        if safe_y_thresh < D:
            val = ((A - D) / (safe_y_thresh - D)) - 1.0
            if val <= 0: return np.nan, r2
            lod_x = C * (val**(1.0 / B))
            if lod_x > max_valid_lod or lod_x < 0: return np.nan, r2
            return lod_x, r2
        else:
            return np.nan, r2
    except:
        return np.nan, 0.0

def run_evaluation(run_dir, exposure_checkpoints, cycle_checkpoints, target_counts, num_replicates, max_workers):
    print("\n=======================================================")
    print(" 🧠 PHASE 2: EXTRACTING MULTI-ALGORITHM LODS")
    print("=======================================================")
    start_eval_time = time.time()

    eval_tasks = []
    for exp_time in exposure_checkpoints:
        exp_dir = os.path.join(run_dir, f"{exp_time}s")
        for n in cycle_checkpoints:
            for rep in range(1, num_replicates + 1):
                rep_dir = os.path.join(exp_dir, f"Rep_{rep}")
                for conc in target_counts:
                    conc_path = os.path.join(rep_dir, f"{conc}_FNDs")
                    if os.path.exists(conc_path):
                        eval_tasks.append((conc_path, n, exp_time, conc, rep))

    algs = ['1. Global Thresholding', '2. Rolling Ball', '3. Single-Frame', '4. Lock-In Amplifier']
    alg_colors = {'1. Global Thresholding': '#d62728', '2. Rolling Ball': '#9467bd', '3. Single-Frame': '#ff7f0e', '4. Lock-In Amplifier': '#2ca02c'}
    results_dict = {alg: {} for alg in algs}

    print(f"🚀 Launching {len(eval_tasks)} Multi-Algorithm evaluation tasks across {max_workers} CPU cores...\n")
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(evaluate_fov_worker, t[0], t[1], t[2], t[3], t[4]) for t in eval_tasks]
        
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(eval_tasks), desc="Evaluation", unit="FOV", ncols=80):
            exp_time, n_cycles, conc, rep, f1, f2, f3, f4 = future.result()
            key = (exp_time, n_cycles, conc)
            for alg, f_val in zip(algs, [f1, f2, f3, f4]):
                if key not in results_dict[alg]: results_dict[alg][key] = []
                results_dict[alg][key].append(f_val)
            
    print(f"\n✅ Parallel Data Extraction finished in {time.time() - start_eval_time:.1f} seconds!")

    # --- TRACKING BEST CONFIGURATIONS ---
    best_configs = {alg: {'lod': np.inf, 'r2': 0.0, 'exp': None, 'cyc': None, 'mean_fluxes': None, 'std_fluxes': None, 'blank_mean': None, 'blank_sd': None} for alg in algs}
    
    max_valid_lod = float(max(target_counts))
    sorted_concs = np.array(sorted(target_counts))
    
    csv_rows = []
    heatmap_data = {alg: {'Exposure (s)': [], 'Cycles': [], 'LOD': [], 'R2': []} for alg in algs}

    for alg in algs:
        for exp_time in exposure_checkpoints:
            for n in cycle_checkpoints:
                mean_fluxes, std_fluxes = [], []
                blank_mean, blank_sd = 0.0, 0.0

                for conc in sorted_concs:
                    fluxes = results_dict[alg].get((exp_time, n, conc), [])
                    m, s = (np.mean(fluxes), np.std(fluxes)) if fluxes else (0.0, 0.0)
                    mean_fluxes.append(m)
                    std_fluxes.append(s)
                    if conc == 0.0: blank_mean, blank_sd = m, max(s, 1e-6)

                lod, r2 = calculate_validated_lod(sorted_concs, np.array(mean_fluxes), np.array(std_fluxes), blank_mean, blank_sd, max_valid_lod)
                
                # Check if this is the best LOD found for this algorithm so far
                if not np.isnan(lod) and lod < best_configs[alg]['lod']:
                    best_configs[alg].update({
                        'lod': lod, 'r2': r2, 'exp': exp_time, 'cyc': n,
                        'mean_fluxes': mean_fluxes, 'std_fluxes': std_fluxes,
                        'blank_mean': blank_mean, 'blank_sd': blank_sd
                    })

                heatmap_data[alg]['Exposure (s)'].append(exp_time)
                heatmap_data[alg]['Cycles'].append(n)
                heatmap_data[alg]['LOD'].append(lod)
                heatmap_data[alg]['R2'].append(r2)

                csv_rows.append({
                    "Algorithm": alg, "Exposure (s)": exp_time, "Cycles": n,
                    "LOD_Calculated": lod, "R_Squared": r2
                })

    output_dir = os.path.join(run_dir, "analysis_output")
    os.makedirs(output_dir, exist_ok=True)
    
    df = pd.DataFrame(csv_rows)
    df.to_csv(os.path.join(output_dir, "fused_4method_results.csv"), index=False)

    # =========================================================
    # 1. GENERATE STANDALONE INDIVIDUAL HEATMAPS (High-Res)
    # =========================================================
    for alg in algs:
        alg_df = pd.DataFrame(heatmap_data[alg])
        plt.figure(figsize=(10, 8))
        ax = plt.gca()
        
        if alg_df['LOD'].isna().all():
            ax.set_facecolor('#e0e0e0')
            ax.text(0.5, 0.5, f"Complete Algorithmic Failure \nGrey = Thermal/Math Failure (R² < {config.MIN_R_SQUARED})", ha='center', va='center', color='red', fontsize=18, fontweight='bold')
        else:
            pivot_lod = alg_df.pivot(index='Cycles', columns='Exposure (s)', values='LOD')
            pivot_lod = pivot_lod.sort_index(ascending=False)
            
            ax.set_facecolor('#e0e0e0') 
            sns.heatmap(pivot_lod, annot=True, fmt=".1f", cmap="viridis_r",
                        cbar_kws={'label': 'LOD (FNDs)'}, linewidths=1.0, annot_kws={"size": 12, "weight": "bold"}, ax=ax)
            
            best = best_configs[alg]
            col_idx = list(pivot_lod.columns).index(best['exp'])
            row_idx = list(pivot_lod.index).index(best['cyc'])
            ax.add_patch(plt.Rectangle((col_idx, row_idx), 1, 1, fill=False, edgecolor='gold', lw=5, clip_on=False))
            ax.text(col_idx + 0.85, row_idx + 0.15, '★', color='gold', fontsize=24, ha='center', va='center')

        plt.title(f"{alg} - Optimization Landscape (N={num_replicates})", fontsize=16, fontweight='bold', pad=15)
        plt.xlabel('Camera Exposure Time (Seconds)', fontsize=14, fontweight='bold')
        plt.ylabel('Microwave Integration (Cycles)', fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        safe_name = alg.replace('. ', '_').replace(' ', '_').replace('-', '_')
        plt.savefig(os.path.join(output_dir, f"Heatmap_Standalone_{safe_name}.png"), dpi=300)
        plt.close()

    # =========================================================
    # 2. GENERATE 4-PANEL MEGA HEATMAP
    # =========================================================
    fig_hm, axes_hm = plt.subplots(2, 2, figsize=(16, 14))
    fig_hm.canvas.manager.set_window_title('4-Method Optimization Showdown')
    fig_hm.suptitle(f"Algorithm Stability Landscape (N={num_replicates} Replicates)\nGrey = Thermal/Math Failure (R² < {config.MIN_R_SQUARED})", 
                 fontsize=18, fontweight='bold', y=0.96)

    for ax, alg in zip(axes_hm.flatten(), algs):
        alg_df = pd.DataFrame(heatmap_data[alg])
        
        if alg_df['LOD'].isna().all():
            ax.set_facecolor('#e0e0e0')
            ax.text(0.5, 0.5, 'Complete Algorithmic Failure', ha='center', va='center', color='red', fontsize=14, fontweight='bold')
            ax.set_title(alg, fontsize=14, fontweight='bold')
            continue

        pivot_lod = alg_df.pivot(index='Cycles', columns='Exposure (s)', values='LOD')
        pivot_lod = pivot_lod.sort_index(ascending=False)
        
        ax.set_facecolor('#e0e0e0') 
        sns.heatmap(pivot_lod, annot=True, fmt=".1f", cmap="viridis_r",
                    cbar_kws={'label': 'LOD (FNDs)'}, linewidths=1.0, annot_kws={"size": 10, "weight": "bold"}, ax=ax)
        
        ax.set_title(alg, fontsize=14, fontweight='bold')
        ax.set_xlabel('Exposure (s)', fontweight='bold')
        ax.set_ylabel('Cycles', fontweight='bold')

        best = best_configs[alg]
        col_idx = list(pivot_lod.columns).index(best['exp'])
        row_idx = list(pivot_lod.index).index(best['cyc'])
        ax.add_patch(plt.Rectangle((col_idx, row_idx), 1, 1, fill=False, edgecolor='gold', lw=4, clip_on=False))
        ax.text(col_idx + 0.85, row_idx + 0.15, '★', color='gold', fontsize=18, ha='center', va='center')

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    plt.savefig(os.path.join(output_dir, "4_Method_Heatmap_Showdown.png"), dpi=300)

    # =========================================================
    # 3. GENERATE 4-PANEL OPTIMAL 4PL CURVE FIGURE
    # =========================================================
    fig_opt, axes_opt = plt.subplots(2, 2, figsize=(14, 12))
    fig_opt.canvas.manager.set_window_title('Optimal 4PL Fits')
    fig_opt.suptitle(f"Optimal 4PL Fitting benchmark between four methods (N={num_replicates} Replicates)", fontsize=18, fontweight='bold', y=0.96)

    for ax, alg in zip(axes_opt.flatten(), algs):
        best = best_configs[alg]
        color = alg_colors[alg]
        
        if best['lod'] == np.inf:
            ax.text(0.5, 0.5, 'No Valid LOD Found\n(R² < 0.90)', ha='center', va='center', color='red', fontsize=14, fontweight='bold')
            ax.set_title(f"{alg}\n(Failed)", fontsize=13, fontweight='bold')
            continue

        x_data = sorted_concs
        y_data = np.array(best['mean_fluxes'])
        y_err = np.array(best['std_fluxes'])
        lod_y = best['blank_mean'] + (3.0 * best['blank_sd'])

        mask_nonzero = x_data > 0
        x_fit, y_fit = x_data[mask_nonzero], y_data[mask_nonzero]
        min_x = np.min(x_fit) if len(x_fit) > 0 else 1
        display_x = np.where(x_data == 0, min_x / 3.0, x_data)

        ax.errorbar(display_x, y_data, yerr=y_err, fmt='o', color=color, ecolor='black', elinewidth=1.5, capsize=4, zorder=5)
        ax.axhline(y=lod_y, color='gray', ls='--', label=f'LOD Threshold')

        # Refit to plot the smooth curve
        guess = [max(0, np.min(y_fit)), 1.0, np.median(x_fit), np.max(y_fit)]
        bounds = ([0, 0, 0, 0], [np.inf, 10.0, np.inf, np.inf])
        popt, _ = curve_fit(four_pl_model, x_fit, y_fit, p0=guess, bounds=bounds, sigma=(y_err[mask_nonzero] + 1e-8), absolute_sigma=False, maxfev=10000)

        smooth_x = np.logspace(np.log10(min_x/3.0), np.log10(np.max(x_fit)*1.2), 100)
        ax.plot(smooth_x, four_pl_model(smooth_x, *popt), color=color, lw=2.5, label=f'Fit (R²={best["r2"]:.3f})')

        ax.axvline(x=best['lod'], color='purple', ls=':', lw=2, label=f'LOD: {best["lod"]:.1f} FNDs')
        ax.plot(best['lod'], lod_y, marker='*', color='gold', ms=14, mec='black', zorder=10)

        ax.set_xscale('log')
        ax.set_title(f"{alg}\n(Optimal Config: {best['exp']}s, {best['cyc']} Cycles)", fontsize=13, fontweight='bold')
        ax.set_xlabel("Number of True FNDs per FOV")
        ax.set_ylabel("Total Integrated Flux (16-bit e-)")
        ax.set_xticks([min_x / 3.0] + list(x_fit))
        ax.set_xticklabels(['0'] + [str(int(x)) for x in x_fit])
        ax.grid(True, which='major', alpha=0.6)
        ax.legend(loc='upper left', fontsize=9)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    plt.savefig(os.path.join(output_dir, "4_Method_Optimal_4PL_Curves.png"), dpi=300)
    
    print(f"\n💾 Graphics processing complete. All files saved to: {output_dir}")
    plt.show()