# =====================================================================
# CONFIG.PY - STATIC PHYSICS & ALGORITHM CONSTANTS
# =====================================================================

# --- 1. PARTICLE & SIGNAL PHYSICS ---
ODMR_DROP = 0.02         
FND_PHYSICS = {
    "100nm": {"PHOTON_YIELD": 2000.0, "JUNK_COUNT": 200, "FAKE_FND_COUNT": 20},
    "600nm": {"PHOTON_YIELD": 40000.0, "JUNK_COUNT": 200, "FAKE_FND_COUNT": 10}
}

# --- 2. ALGORITHM & IMAGE PROCESSING SETTINGS ---
ALG_MAD_MULTIPLIER = 4.0          
ALG_GAUSSIAN_SIGMA = 1.0          
ALG_TOPHAT_DISK_SIZE = 20         
ALG_DOG_LOW_SIGMA = 1.0           
ALG_DOG_HIGH_SIGMA = 5.0          
ALG_ALIGN_UPSAMPLE = 10           
ALG_MAX_DRIFT = 15.0              

# --- 3. CLINICAL VALIDATION FILTERS ---
MIN_SIGNAL_RISE = 1.2
MIN_R_SQUARED = 0.90              

# --- 4. BASE OPTICS & CAMERA NOISE ---
LENS_POWER = "40x_binned"         
CAMERA_SATURATION = 4095.0        
DARK_CURRENT_RATE = 15.0          
BACKGROUND_PHOTONS = 2000.0       
BACKGROUND_GRAININESS_STD = 0.5   
SENSOR_CROSSTALK = 0.65           
EXCESS_SHOT_NOISE_MULTIPLIER = 1.2
VIGNETTING_STRENGTH = 0.4         

# --- 5. THERMODYNAMICS & FLUID DYNAMICS ---
ODMR_THERMAL_HALF_LIFE = 10.0     
LASER_DIMMING_PER_SEC = 0.015     
LASER_INSTABILITY = 0.02          
B1_MICROWAVE_GRADIENT = 0.25      
THERMAL_LENSING_SHIFT = 0.10      
Z_AXIS_FOCAL_DRIFT = 0.2          
DRIFT_PX_PER_SEC = 0.5            
BACKGROUND_CLOUDINESS = 0.4       
BIO_GRAIN_SIZE = 1.2              
BIO_GRAIN_CONTRAST = 0.015         
CLUSTERING_PROBABILITY = 0.2      
JUNK_CLUSTERING_PROBABILITY = 0.5 
FLOATING_DEBRIS_FRACTION = 0.3    
FLUID_FLOW_X = 0.5                
FLUID_FLOW_Y = -0.5               
BROWNIAN_WOBBLE_STD = 0.8         

# --- 6. ADVANCED ENGINE TUNING ---
PSF_SIGMA = 1.2                   
AIRY_RING_MULTIPLIER = 5.0        
PSF_KERNEL_SIZE = 41              
ILLUM_CENTER_X_RATIO = 0.45       
ILLUM_CENTER_Y_RATIO = 0.50       
ILLUM_SPREAD = 0.6                
MACRO_CLOUD_SIGMA = 45.0          
DEBRIS_SCALE_MEAN = 3.5           
DRIFT_RANDOM_NOISE = 0.3