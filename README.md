# FluoroLock: Digital Twin Simulator for Fluorescent Nanodiamond Assays

![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)
![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)

FluoroLock is a high-fidelity, physics-based digital twin simulator and benchmarking suite designed for **Fluorescent Nanodiamond (FND) Lock-In Optical Imaging**. 

This platform enables researchers to simulate realistic diagnostic imaging scenarios with ultra-low Limit of Detection (LOD), incorporating optical diffraction, fluid dynamics, hardware-induced drift, and complex biological backgrounds. It provides a robust framework to evaluate imaging algorithms against a hardware-aware Digital Lock-In Amplifier.

---

## 📊 Visual Showcase

### 1. Raw Simulation Data (The Digital Twin)
> **Figure 1:** A 2x4 grid showcasing the simulated Field of View across four FND concentrations. **(Simulated for 100nm FNDs under a 40x objective)**. The top row represents the microwave OFF state (max fluorescence), and the bottom row represents the microwave ON state (ODMR quenching).
![Simulated ON/OFF Images](assets/Simulation_Grid_2x4.png)

### 2. Algorithm Benchmark Showdown
> **Figure 2:** Comparison of classical imaging techniques against the Digital Lock-In method **(n=3 replicates, 100nm FNDs)**. The graph illustrates how lock-in integration suppresses the background noise floor, lowering the LOD as integration cycles increase. Error bars represent the standard deviation of raw flux across replicates.
![Benchmark Showdown](assets/Benchmark_Showdown_Quad_ErrorBars.png)

### 3. Lock-In Performance Optimization
> **Figure 3:** Dynamic performance of the Lock-In Amplifier over time **(n=3 replicates)**. The Limit of Detection (LOD) at each checkpoint is deterministically calculated by pooling the statistical variance across all replicates to ensure rigorous curve fitting. The algorithm automatically flags the optimal integration cycle (lowest LOD) required to achieve maximum assay sensitivity.
![Optimization Curve](assets/LockIn_Optimization_Curve.png)

---

## ⚙️ Mechanism: How it Works

The core challenge in point-of-care fluorescence assays is **background autofluorescence** from biological samples. FluoroLock models a quantum-sensing solution using the Nitrogen-Vacancy (NV) centers in FNDs.

### The Physics Engine (`run_simulator.py`)
The simulator generates time-resolved image stacks by modeling:
* **Optical PSF Convolution:** Static and floating particles are convolved with an Airy disk Point Spread Function to mimic diffraction-limited imaging.
* **Cumulative Random Walks:** Simulates Brownian motion ($MSD \propto t$) and directional fluid flow, causing non-specific debris to wander or drift across the FOV.
* **Hardware Thermodynamics:** Models low-cost hardware constraints, including thermal focal sag (Z-drift), mechanical stage vibration (XY-drift), and microwave-induced thermal lensing.

### The Lock-In Pipeline (`run_lockin_optimization.py`)
The demodulation process follows a rigorous signal processing workflow:
1.  **Drift Correction:** Uses phase cross-correlation to track and reverse spatial drift relative to a reference frame.
2.  **Pixel-wise Demodulation:** Integrates and subtracts synchronized ON and OFF frames to isolate modulating FND signals from static or slowly bleaching background noise.
3.  **Statistical Isolation:** Employs Median Absolute Deviation (MAD) to dynamically set signal thresholds above the CMOS read noise floor.

---

## 🎛️ Parameter Tuning & Recommendations (`config.py`)

All environmental and hardware variables are centralized in `config.py`. Below are the recommended ranges for achieving realistic biological simulations.

### 1. Sensor & Optics
| Parameter | Description | Realistic Range | Recommendation |
| :--- | :--- | :--- | :--- |
| `PSF_SIGMA` | Blur radius of the optical system. | `0.6 - 1.5` | Use `1.2` for typical 40x objectives. |
| `BACKGROUND_PHOTONS` | Baseline fluid autofluorescence. | `200 - 1500` | Higher values mimic "dirty" clinical samples. |
| `CAMERA_SATURATION` | Max pixel intensity. | `255 - 4095` | `4095` (12-bit) for scientific CMOS sensors. |

### 2. Biological Background (Fixed Factors)
*For valid LOD calculation, keep these fixed across all concentrations to represent constant non-specific binding.*

| Parameter | Description | Recommendation |
| :--- | :--- | :--- |
| `JUNK_COUNT` | Number of large debris blobs. | `150 - 300` for realistic complexity. |
| `FAKE_FND_COUNT` | Non-blinking point-source "imposters". | `30 - 60` to test algorithm specificity. |
| `FLOATING_DEBRIS_FRACTION`| Ratio of particles in fluid vs on glass. | `0.2 - 0.4` is typical for wet mounts. |

### 3. Drift & Dynamics
| Parameter | Description | Recommendation |
| :--- | :--- | :--- |
| `DRIFT_PX` | Total mechanical stage drift. | `< 3.0` for stable setups; higher for DIY. |
| `BROWNIAN_WOBBLE_STD` | Step size of random walk. | `0.5 - 1.0` for standard aqueous buffers. |
| `FLUID_FLOW_X/Y` | Linear directional drift. | Set to `0.0` for sealed chips, `1.5` for drying slides. |

---

## 🚀 Installation & Usage

### Project Structure
```text
fluorolock/
├── config.py                  # Shared master dashboard
├── run_simulator.py           # Physics-based image generation
├── run_benchmark.py           # Multi-algorithm comparison suite
├── run_lockin_optimization.py # Focused Lock-In performance analysis
├── assets/                    # Visualization figures
└── data/                      # Simulation outputs and fused CSV results
```

### Quick Start
1.  **Clone & Install:**
    ```bash
    git clone https://github.com/YourUsername/fluorolock.git
    cd fluorolock
    pip install -r requirements.txt
    ```
2.  **Generate Data:**
    ```bash
    python run_simulator.py
    ```
3.  **Analyze Performance:**
    ```bash
    python run_benchmark.py
    ```

---

## 🧠 Downstream Research: AI Implementation
Datasets generated by FluoroLock are specifically structured to train spatiotemporal models like **Video Vision Transformers (ViViT)**. The explicit separation of Brownian motion from microwave-synchronized blinking provides a high-quality ground truth for training AI to differentiate between biological artifacts and target biomarkers in point-of-care diagnostics.

