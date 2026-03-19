# =====================================================================
# METHODS.PY - IMAGE PROCESSING & ALGORITHMS
# =====================================================================
import os
import numpy as np
from PIL import Image
from scipy.ndimage import shift
from skimage import filters
from skimage.registration import phase_cross_correlation
from skimage.morphology import white_tophat, disk
import config

def _load_image(img_path):
    img_arr = np.array(Image.open(img_path))
    if img_arr.ndim == 3: return img_arr[:, :, 0].astype(np.float64)
    return img_arr.astype(np.float64)

def evaluate_fov_worker(conc_path, n_cycles, exp_time, conc, rep):
    """Parallel-safe worker that runs all 4 algorithms on a single FOV."""
    on_dir = os.path.join(conc_path, "ON")
    off_dir = os.path.join(conc_path, "OFF")
    
    if not os.path.exists(on_dir) or not os.path.exists(off_dir):
        return (exp_time, n_cycles, conc, rep, 0.0, 0.0, 0.0, 0.0)

    on_files = sorted([os.path.join(on_dir, f) for f in os.listdir(on_dir) if f.endswith(('.tif', '.tiff'))])
    off_files = sorted([os.path.join(off_dir, f) for f in os.listdir(off_dir) if f.endswith(('.tif', '.tiff'))])
    
    actual_n = min(n_cycles, len(on_files), len(off_files))
    if actual_n == 0: 
        return (exp_time, n_cycles, conc, rep, 0.0, 0.0, 0.0, 0.0)

    img_raw = _load_image(off_files[0])

    # --- 1. Global Thresholding ---
    img_smooth = filters.gaussian(img_raw, sigma=config.ALG_GAUSSIAN_SIGMA, preserve_range=True)
    med_1 = np.median(img_smooth)
    mad_1 = np.median(np.abs(img_smooth - med_1)) * 1.4826
    if mad_1 == 0: mad_1 = np.std(img_smooth)
    pixels_alg1 = img_smooth[img_smooth > med_1 + (config.ALG_MAD_MULTIPLIER * mad_1)]
    flux_alg1 = np.sum(pixels_alg1) if len(pixels_alg1) > 0 else 0.0

    # --- 2. Rolling Ball Subtraction ---
    img_rb = white_tophat(img_raw, footprint=disk(config.ALG_TOPHAT_DISK_SIZE))
    img_rb_smooth = filters.gaussian(img_rb, sigma=config.ALG_GAUSSIAN_SIGMA, preserve_range=True)
    med_rb = np.median(img_rb_smooth)
    mad_rb = np.median(np.abs(img_rb_smooth - med_rb)) * 1.4826
    if mad_rb == 0: mad_rb = np.std(img_rb_smooth)
    pixels_alg2 = img_rb_smooth[img_rb_smooth > med_rb + (config.ALG_MAD_MULTIPLIER * mad_rb)]
    flux_alg2 = np.sum(pixels_alg2) if len(pixels_alg2) > 0 else 0.0

    # --- 3. Single-Frame Subtraction ---
    img_on_raw = _load_image(on_files[0])
    diff_raw = img_raw - img_on_raw
    diff_bandpass = (filters.gaussian(diff_raw, sigma=config.ALG_DOG_LOW_SIGMA) - 
                     filters.gaussian(diff_raw, sigma=config.ALG_DOG_HIGH_SIGMA))
    med_3 = np.median(diff_bandpass)
    mad_3 = np.median(np.abs(diff_bandpass - med_3)) * 1.4826
    if mad_3 == 0: mad_3 = np.std(diff_bandpass)
    pixels_alg3 = diff_bandpass[diff_bandpass > med_3 + (config.ALG_MAD_MULTIPLIER * mad_3)]
    flux_alg3 = np.sum(pixels_alg3) if len(pixels_alg3) > 0 else 0.0

    # --- 4. Digital Lock-In Amplifier ---
    lockin_sum = np.zeros_like(img_raw, dtype=np.float64)
    for i in range(actual_n):
        off_img = _load_image(off_files[i])
        on_img = _load_image(on_files[i])
        
        s, _, _ = phase_cross_correlation(img_raw, off_img, upsample_factor=config.ALG_ALIGN_UPSAMPLE)
        if np.max(np.abs(s)) > config.ALG_MAX_DRIFT: s = [0.0, 0.0]
            
        delta_img = off_img - on_img
        lockin_sum += shift(delta_img, shift=s, mode='nearest')

    lockin_avg = lockin_sum / actual_n
    lockin_bandpass = (filters.gaussian(lockin_avg, sigma=config.ALG_DOG_LOW_SIGMA) - 
                       filters.gaussian(lockin_avg, sigma=config.ALG_DOG_HIGH_SIGMA))
    
    med_4 = np.median(lockin_bandpass)
    mad_4 = np.median(np.abs(lockin_bandpass - med_4)) * 1.4826
    if mad_4 == 0: mad_4 = np.std(lockin_bandpass)
    pixels_alg4 = lockin_bandpass[lockin_bandpass > med_4 + (config.ALG_MAD_MULTIPLIER * mad_4)]
    flux_alg4 = np.sum(pixels_alg4) if len(pixels_alg4) > 0 else 0.0

    return (exp_time, n_cycles, conc, rep, flux_alg1, flux_alg2, flux_alg3, flux_alg4)