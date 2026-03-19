# FluoroLock: Digital Twin Simulator for Fluorescent Nanodiamond Assays

FluoroLock is a highly modular, multithreaded digital twin physics engine and algorithmic evaluator for widefield Fluorescence Nanodiamond (FND) imaging. It is specifically designed to simulate and optimize point-of-care (POCT) optical setups, such as Raspberry Pi-based microscopes, for Digital Western Blots and Lateral Flow Assays (LFA).

This pipeline physically simulates background autofluorescence, thermal lensing, thermodynamic stage drift, laser photobleaching, and camera CMOS noise. It then benchmarks four distinct image processing algorithms—including our robust **Digital Lock-In Amplifier**—to determine the optimal limit of detection (LOD) across various microwave integration cycles and camera exposure times.

---

## 📊 Performance & Showdown Visualizations

The pipeline automatically generates publication-ready comparative analyses and visual showcases of the physical simulation states.

### 1. Simulated FND Optical Response (ON vs. OFF)

![12-bit Raw FND Showcase](assets/12bit_raw_grid_showcase.png)
*Figure 1: 12-bit Raw Sensor Output. A 2x4 grid showcasing the true physical 12-bit response of the microwave ON and OFF states before downscaling.*

![Visual Red FND Showcase](assets/visual_red_grid_showcase.png)
*Figure 2: VISUAL_RED Presentation Mapping. A 2x4 grid demonstrating strictly-mapped 8-bit visual representations, mathematically preserving the true ODMR contrast ratios without artificial auto-scaling.*

### 2. Multi-Algorithm Benchmarking

![4-Method Heatmap Showdown](assets/4_Method_Heatmap_Showdown.png)
*Figure 3: Algorithm Stability Landscape. Shows the thermal and mathematical failure points of traditional methods versus the Lock-In Amplifier across different hardware exposure and cycle times.*

![Optimal 4PL Curves](assets/4_Method_Optimal_4PL_Curves.png)
*Figure 4: Optimal 4PL Fitting Curves. Demonstrates the mathematical Limits of Detection (LOD) achieved by each algorithm at its individually optimized hardware setting.*

---

## 🚀 Architecture

This new release introduces a unified, 5-file object-oriented architecture. **Everything is controlled and executed from `main.py`.**

* `main.py` - The Control Center. Run this to execute your sweeps and evaluations.
* `config.py` - The Physics Engine. Contains static thermodynamic, optical, and algorithm constants.
* `simulator.py` - The multithreaded generator that builds 12-bit TIFF stacks of physical FOVs.
* `evaluator.py` - The 4-method benchmarking engine that outputs 2x2 heatmaps and 4PL curves.
* `methods.py` - The isolated image processing math (Global Thresholding, Rolling Ball, Single-Frame, Lock-In).

---

## 💻 Usage & Quick Start

### 1. Installation
Clone the repository and install the required dependencies:
```bash
git clone https://github.com/YourUsername/lock-in-effect-imaging-twin.git
cd lock-in-effect-imaging-twin
pip install -r requirements.txt
```

### 2. Execution
To run a full hardware sweep and algorithm evaluation, simply configure your experimental matrix in `main.py` and run:
```bash
python main.py
```

### 3. Output Directory Structure
Data is automatically routed into a unified auto-incrementing folder system to prevent overwriting.
```text
data/
└── 100nm_run1/
    ├── 0.25s/
    │   └── Rep_1/
    │       └── 50_FNDs/
    │           ├── ON/            # Raw 12-bit TIFFs (Microwave ON)
    │           ├── OFF/           # Raw 12-bit TIFFs (Microwave OFF)
    │           └── VISUAL_RED/    # Strictly-mapped 8-bit PNGs for presentation
    └── analysis_output/
        ├── fused_4method_results.csv
        ├── Heatmap_Standalone_Lock_In_Amplifier.png
        ├── 4_Method_Heatmap_Showdown.png
        └── 4_Method_Optimal_4PL_Curves.png
```

---

## PART 1: Routine Sweep Controls (`main.py`)

These are the frequently changed parameters that govern your experimental matrix. They dictate *what* you are testing and sweeping. Modify these directly inside `main.py`.

| Parameter | Description | Suggested Range / Options |
| :--- | :--- | :--- |
| **`EXECUTION_MODE`** | Controls the pipeline phase. | `"simulate_only"`, `"evaluate_only"`, `"run_both"` |
| **`TARGET_RUN_FOLDER`** | Tells the evaluator which data to analyze if you skipped simulation. | `"latest"` (auto-grabs newest), or string (e.g., `"100nm_run2"`) |
| **`EXPOSURE_CHECKPOINTS`** | The camera integration times to simulate. Longer exposures increase background thermal noise. | `[0.1, 0.25, 0.5, 1.0]` seconds |
| **`CYCLE_CHECKPOINTS`** | Total number of Microwave ON/OFF modulations to extract signal from. | `[1, 5, 10, 20, 50, 80, 100]` |
| **`TARGET_FND_COUNTS`** | True ground-truth number of FNDs dropped into the simulated FOV. | Logarithmic scale, e.g., `[0, 5, 10, 50, 100, 500]` |
| **`NUM_REPLICATES`** | Number of statistically independent FOVs generated for *every* condition. | `3` (Standard) to `5` (Publication) |
| **`PARTICLE_MODE`** | Selects the physical FND size matrix. | `"100nm"` or `"600nm"` |
| **`MAX_PARALLEL_WORKERS`** | Number of simultaneous Python environments spawned across your CPU. | **Total Logical Processors minus 2** (e.g., `14` for 16-thread CPU) |
| **`SIZE_X` / `SIZE_Y`** | Resolution of the simulated CMOS sensor. | `960` / `720` (2x2 Binning mode) |

---

## PART 2: Advanced Physics & Algorithmic Settings (`config.py`)

These are the deep-engine variables. They define the physical realities of the biological sample, the optical train, and the mathematical thresholds for the algorithms. Modify these inside `config.py`.

### Particle & Signal Physics
| Parameter | Description | Suggested Range / Default |
| :--- | :--- | :--- |
| **`ODMR_DROP`** | Quantum contrast ratio of the NV centers under microwave resonance. | `0.01` (Dirty) to `0.03` (Perfect). Default: `0.02` |
| **`PHOTON_YIELD`** | Theoretical flux of photons emitted by a single FND per second reaching the sensor. | `2000.0` (100nm) / `5000.0` (600nm - capped to prevent saturation) |

### Clinical Validation Filters
| Parameter | Description | Suggested Range / Default |
| :--- | :--- | :--- |
| **`MIN_SIGNAL_RISE`** | Multiplier over the blank background required to consider a curve valid. | `1.2` (20% above noise) to `1.5` |
| **`MIN_R_SQUARED`** | Minimum coefficient of determination for the 4PL curve fit. | `0.90` (Standard) to `0.95` (Clinical) |

### Algorithm Processing Thresholds
| Parameter | Description | Suggested Range / Default |
| :--- | :--- | :--- |
| **`ALG_MAD_MULTIPLIER`** | Strictness of the signal thresholding (x * Median Absolute Deviation). | `3.0` to `5.0`. Default: `4.0` |
| **`ALG_TOPHAT_DISK_SIZE`** | Structural element size for Rolling Ball background subtraction. | `15` to `30` pixels |
| **`ALG_DOG_LOW_SIGMA`** / **`HIGH`** | Bandpass limits for the Difference of Gaussians (DoG) filter. | Low: `0.5 - 1.5`, High: `3.0 - 7.0` |
| **`ALG_ALIGN_UPSAMPLE`** | Sub-pixel resolution factor for cross-correlation mechanical drift correction. | `10` (0.1 px) to `100` (0.01 px, extremely slow) |

### Base Optics & Camera Noise
| Parameter | Description | Suggested Range / Default |
| :--- | :--- | :--- |
| **`CAMERA_SATURATION`** | Physical well depth limit of the simulated sensor. | `4095.0` (12-bit uncompressed RAW) |
| **`BACKGROUND_PHOTONS`** | Base autofluorescence of the nitrocellulose membrane/tissue. | `1000.0` (Clean) to `3000.0` (Dirty) |
| **`DARK_CURRENT_RATE`** | Thermal electrons accumulating per pixel per second. | `5.0` (Cooled) to `25.0` (Uncooled) |
| **`EXCESS_SHOT_NOISE_MULTIPLIER`**| Amplifies the standard Poisson noise. | `1.0` to `1.5` |

### Thermodynamics & Fluid Dynamics
| Parameter | Description | Suggested Range / Default |
| :--- | :--- | :--- |
| **`ODMR_THERMAL_HALF_LIFE`** | Seconds of microwave exposure before thermal expansion destroys tracking. | `5.0` to `20.0` seconds |
| **`LASER_DIMMING_PER_SEC`** | Photobleaching rate of the background tissue (FNDs do not bleach). | `0.01` (1%/sec) to `0.05` |
| **`DRIFT_PX_PER_SEC`** | Mechanical XYZ stage drift caused by thermal expansion. | `0.1` (Stable) to `1.5` (Unstable chassis) |
| **`THERMAL_LENSING_SHIFT`** | Artificial focus-shift factor induced by microwave heating. | `0.05` to `0.3` |
| **`BIO_GRAIN_CONTRAST`** | Controls the clumpiness contrast of the biological junk. | `0.05` to `0.20` |
| **`BACKGROUND_CLOUDINESS`** | Controls the macroscopic cloudiness of the biological junk. | `0.2` to `0.6` |

### Advanced Engine Tuning (Developers Only)
| Parameter | Description | Suggested Range / Default |
| :--- | :--- | :--- |
| **`PSF_SIGMA`** | Physical spread of the Point Spread Function (Airy Disk). | `1.0` to `2.0` (Depends on NA) |
| **`AIRY_RING_MULTIPLIER`** | Artificially brightens outer diffraction rings to challenge alignment algorithms. | `2.0` to `6.0` |
| **`ILLUM_CENTER_X_RATIO`** / **`Y`**| Defines the Gaussian beam profile center (0.5 is perfectly centered). | `0.45` to `0.55` (Simulates misalignment) |
| **`ILLUM_SPREAD`** | Defines the Gaussian beam profile spread. | `0.5` to `0.8` |
