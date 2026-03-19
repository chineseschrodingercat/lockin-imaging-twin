# =====================================================================
# SIMULATOR.PY - PHYSICS ENGINE & GENERATION
# =====================================================================
import os
import time
import numpy as np
import cv2  
from PIL import Image
from scipy.ndimage import gaussian_filter
from scipy.signal import fftconvolve
from scipy.special import j1
import concurrent.futures  
from tqdm import tqdm
import config

def fast_shift(image, shift_y, shift_x):
    M = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
    return cv2.warpAffine(image, M, (image.shape[1], image.shape[0]), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_REPLICATE)

def generate_airy_psf(sigma, ring_boost, size=41):
    y, x = np.meshgrid(np.arange(size) - size//2, np.arange(size) - size//2)
    r = np.sqrt(x**2 + y**2)
    z = r * (3.8317 / (2.5 * sigma))
    z[size//2, size//2] = 1e-8 
    psf = (2 * j1(z) / z)**2
    ring_mask = z > 3.8317
    psf[ring_mask] = psf[ring_mask] * ring_boost 
    return psf / np.max(psf)

def simulate_single_fov(rep, fnd_count, psf_start, psf_end, xx, yy, b1_gradient, illum, cloud_mult, grain_mult, dynamic_data_root, dynamic_exposure_time, max_cycles, particle_mode, size_x, size_y):
    active_fnd = config.FND_PHYSICS[particle_mode]
    
    conc_dir = os.path.join(dynamic_data_root, f"Rep_{rep}", f"{fnd_count}_FNDs")
    on_dir, off_dir = os.path.join(conc_dir, "ON"), os.path.join(conc_dir, "OFF")
    vis_dir = os.path.join(conc_dir, "VISUAL_RED") 
    os.makedirs(on_dir, exist_ok=True)
    os.makedirs(off_dir, exist_ok=True)
    os.makedirs(vis_dir, exist_ok=True)
    
    debris_static = np.zeros((size_y, size_x))
    debris_floating = np.zeros((size_y, size_x))
    locs = []

    def get_loc(prob):
        if len(locs) > 0 and np.random.rand() < prob:
            bx, by = locs[np.random.randint(0, len(locs))]
            x = np.clip(bx + np.random.randint(-4, 4), 20, size_x - 20)
            y = np.clip(by + np.random.randint(-4, 4), 20, size_y - 20)
        else:
            x, y = np.random.randint(20, size_x - 20), np.random.randint(20, size_y - 20)
        locs.append((x, y))
        return x, y

    for _ in range(active_fnd["JUNK_COUNT"]):
        x, y = get_loc(config.JUNK_CLUSTERING_PROBABILITY)
        scale = np.random.exponential(scale=config.DEBRIS_SCALE_MEAN) + 1.5 
        amp = np.random.uniform(300.0, active_fnd["PHOTON_YIELD"] * 1.2) 
        
        y_min, y_max = max(0, int(y - scale*4)), min(size_y, int(y + scale*4) + 1)
        x_min, x_max = max(0, int(x - scale*4)), min(size_x, int(x + scale*4) + 1)
        
        if y_max > y_min and x_max > x_min:
            box_x, box_y = xx[y_min:y_max, x_min:x_max], yy[y_min:y_max, x_min:x_max]
            envelope = np.exp(-((box_x - x)**2 + (box_y - y)**2) / (2 * scale**2))
            blob = envelope * amp
            
            if np.random.rand() < config.FLOATING_DEBRIS_FRACTION:
                debris_floating[y_min:y_max, x_min:x_max] += blob
            else:
                debris_static[y_min:y_max, x_min:x_max] += blob

    real_dots = np.zeros((size_y, size_x))
    for _ in range(fnd_count):
        x, y = get_loc(config.CLUSTERING_PROBABILITY)
        real_dots[y, x] += 1.0
    
    real_start = fftconvolve(real_dots, psf_start, mode='same')
    real_end = fftconvolve(real_dots, psf_end, mode='same')

    current_flow_x, current_flow_y = 0.0, 0.0
    cycle_duration = dynamic_exposure_time * 2.0  
    cumulative_mw_on_time = 0.0 

    for i in range(max_cycles):
        real_time_sec = i * cycle_duration
        thermal_stress_factor = min(1.0, (real_time_sec / config.ODMR_THERMAL_HALF_LIFE) ** 2)
        laser_bleach = max(0.1, 1.0 - (config.LASER_DIMMING_PER_SEC * real_time_sec))
        laser_flicker = np.random.normal(1.0, config.LASER_INSTABILITY)
        
        current_real = (real_start * (1.0 - thermal_stress_factor)) + (real_end * thermal_stress_factor)
        
        if i > 0:
            current_flow_x += (config.FLUID_FLOW_X * cycle_duration) + np.random.normal(0, config.BROWNIAN_WOBBLE_STD)
            current_flow_y += (config.FLUID_FLOW_Y * cycle_duration) + np.random.normal(0, config.BROWNIAN_WOBBLE_STD)
        
        motion_blur_sigma = max(0.1, np.sqrt(config.FLUID_FLOW_X**2 + config.FLUID_FLOW_Y**2) * dynamic_exposure_time)
        blurred_floating = cv2.GaussianBlur(debris_floating, (0, 0), sigmaX=motion_blur_sigma, sigmaY=motion_blur_sigma)
        curr_floating = fast_shift(blurred_floating, current_flow_y, current_flow_x)
        
        curr_fog = fast_shift(cloud_mult * grain_mult, current_flow_y, current_flow_x)
        curr_junk = debris_static + curr_floating
        
        photon_yield_frame = active_fnd["PHOTON_YIELD"] * dynamic_exposure_time
        bg_photons_frame = config.BACKGROUND_PHOTONS * dynamic_exposure_time

        fnd_off = current_real * photon_yield_frame * laser_flicker * illum
        current_odmr_efficiency = np.exp(-cumulative_mw_on_time / config.ODMR_THERMAL_HALF_LIFE)
        dynamic_odmr_drop = config.ODMR_DROP * current_odmr_efficiency
        dynamic_odmr_map = dynamic_odmr_drop * b1_gradient
        
        fnd_on  = fnd_off * (1.0 - dynamic_odmr_map)
        cumulative_mw_on_time += dynamic_exposure_time
        
        junk_light = curr_junk * dynamic_exposure_time * laser_bleach * laser_flicker * illum
        base_fog = bg_photons_frame * illum * curr_fog * laser_bleach * laser_flicker
        
        off_pure = fnd_off + junk_light + base_fog
        
        current_lensing_shift = config.THERMAL_LENSING_SHIFT * (1.0 + thermal_stress_factor)
        fog_on = fast_shift(base_fog, 0, current_lensing_shift) if current_lensing_shift > 0 else base_fog
        on_pure = fnd_on + junk_light + fog_on
        
        dx = (config.DRIFT_PX_PER_SEC * real_time_sec) + np.random.normal(0, config.DRIFT_RANDOM_NOISE)
        dy = (config.DRIFT_PX_PER_SEC * real_time_sec) + np.random.normal(0, config.DRIFT_RANDOM_NOISE)
        
        def apply_camera_physics(pure_img, sx, sy):
            shifted = fast_shift(pure_img, sy, sx)
            noisy = shifted + np.random.normal(0, np.sqrt(np.clip(shifted, 0, None))) * config.EXCESS_SHOT_NOISE_MULTIPLIER
            dark_electrons = dynamic_exposure_time * config.DARK_CURRENT_RATE
            noisy += np.random.poisson(dark_electrons, size=noisy.shape)
            read_noise = np.random.normal(0, config.BACKGROUND_GRAININESS_STD, size=noisy.shape)
            if config.SENSOR_CROSSTALK > 0:
                read_noise = cv2.GaussianBlur(read_noise, (0, 0), sigmaX=config.SENSOR_CROSSTALK, sigmaY=config.SENSOR_CROSSTALK)
            return np.clip(noisy + read_noise, 0, config.CAMERA_SATURATION)

        def save_outputs(electrons, directory, vis_directory, filename):
            img_16bit = electrons.astype(np.uint16)
            Image.fromarray(img_16bit, mode='I;16').save(os.path.join(directory, f"{filename}.tif"))
            frame_max = np.max(electrons)
            if frame_max == 0: frame_max = 1.0 
            img_8bit = np.clip((electrons / frame_max) * 255, 0, 255).astype(np.uint8)
            rgb_vis = np.zeros((size_y, size_x, 3), dtype=np.uint8)
            rgb_vis[:, :, 0] = img_8bit 
            Image.fromarray(rgb_vis, mode='RGB').save(os.path.join(vis_directory, f"{filename}_RED.png"))

        save_outputs(apply_camera_physics(off_pure, dx, dy), off_dir, vis_dir, f"frame_{i:02d}_OFF")
        save_outputs(apply_camera_physics(on_pure, dx, dy), on_dir, vis_dir, f"frame_{i:02d}_ON")
        
    return f"Simulated: Rep {rep} | {fnd_count} FNDs"

def run_sweep(run_dir, exposure_checkpoints, cycle_checkpoints, target_counts, num_replicates, size_x, size_y, particle_mode, max_workers):
    print("\n=======================================================")
    print(" 🛠️ PHASE 1: GENERATING 3D PHYSICS DATA")
    print("=======================================================")
    start_time = time.time()
    
    sigma_start = config.PSF_SIGMA
    sigma_end = sigma_start + config.Z_AXIS_FOCAL_DRIFT
    psf_start = generate_airy_psf(sigma=sigma_start, ring_boost=config.AIRY_RING_MULTIPLIER, size=config.PSF_KERNEL_SIZE)
    psf_end = generate_airy_psf(sigma=sigma_end, ring_boost=config.AIRY_RING_MULTIPLIER, size=config.PSF_KERNEL_SIZE)
    
    xx, yy = np.meshgrid(np.arange(size_x), np.arange(size_y))
    b1_gradient = 1.0 - (config.B1_MICROWAVE_GRADIENT * (xx / size_x))
    
    cx, cy = size_x * config.ILLUM_CENTER_X_RATIO, size_y * config.ILLUM_CENTER_Y_RATIO
    illum = np.exp(-(((xx - cx)**2) + ((yy - cy)**2)) / (2 * (size_x * config.ILLUM_SPREAD)**2))
    illum = illum * config.VIGNETTING_STRENGTH + (1.0 - config.VIGNETTING_STRENGTH)

    macro_noise = np.random.normal(0, 1, (size_y, size_x))
    smooth_clouds = cv2.GaussianBlur(macro_noise, (0, 0), sigmaX=config.MACRO_CLOUD_SIGMA, sigmaY=config.MACRO_CLOUD_SIGMA)
    smooth_clouds = (smooth_clouds - np.min(smooth_clouds)) / (np.max(smooth_clouds) - np.min(smooth_clouds))
    cloud_mult = (smooth_clouds * config.BACKGROUND_CLOUDINESS * 2.0) + (1.0 - config.BACKGROUND_CLOUDINESS)

    micro_noise = np.random.normal(0, 1, (size_y, size_x))
    bio_grain = cv2.GaussianBlur(micro_noise, (0, 0), sigmaX=config.BIO_GRAIN_SIZE, sigmaY=config.BIO_GRAIN_SIZE)
    bio_grain = (bio_grain - np.mean(bio_grain)) / (np.std(bio_grain) + 1e-8)
    grain_mult = np.clip(1.0 + (bio_grain * config.BIO_GRAIN_CONTRAST), 0.1, 3.0)

    max_cycles = max(cycle_checkpoints)
    tasks = []
    
    for exp_time in exposure_checkpoints:
        exp_data_root = os.path.join(run_dir, f"{exp_time}s")
        for rep in range(1, num_replicates + 1):
            for fnd_count in target_counts:
                tasks.append((rep, fnd_count, exp_data_root, exp_time, max_cycles, particle_mode, size_x, size_y))

    print(f"🚀 Dispatching {len(tasks)} physical FOV simulations across {max_workers} CPU cores...\n")
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(simulate_single_fov, t[0], t[1], psf_start, psf_end, xx, yy, b1_gradient, illum, cloud_mult, grain_mult, t[2], t[3], t[4], t[5], t[6], t[7]) 
                   for t in tasks]
        
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(tasks), desc="Simulation Progress", unit="FOV", ncols=80):
            pass 

    print(f"\n🎉 Simulation Engine Complete in {time.time() - start_time:.1f} seconds!")