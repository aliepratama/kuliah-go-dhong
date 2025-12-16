"""
YOLOv11 ML Engine for Leaf Area Detection.
Refactored from inference.py for web service use.
"""
import cv2
import numpy as np
from ultralytics import YOLO
from pathlib import Path
from datetime import datetime
import io
from PIL import Image

# Constants
COIN_DIAMETER_MM = 27.2  # Aluminum 500 IDR (Silver)
COIN_TRUE_AREA_MM2 = np.pi * ((COIN_DIAMETER_MM / 2) ** 2)  # ~581.05 mm²

# Global model (load once)
MODEL_PATH = "models/best.pt"
model = None


def load_model():
    """Load YOLO model (called once at startup)."""
    global model
    if model is None:
        print(f"🔄 Loading YOLOv11-seg model from {MODEL_PATH}...")
        model = YOLO(MODEL_PATH)
        print(f"✅ Model loaded successfully. Classes: {model.names}")
    return model


def calculate_polygon_area(polygon_coords):
    """
    Calculate area of polygon using Shoelace formula.
    
    Args:
        polygon_coords: Array of (x, y) coordinates
        
    Returns:
        Area in pixels²
    """
    if len(polygon_coords) < 3:
        return 0.0
    
    x = polygon_coords[:, 0]
    y = polygon_coords[:, 1]
    
    # Shoelace formula
    area = 0.5 * np.abs(
        np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))
    )
    
    return area


def process_image(image_bytes: bytes, save_dir: str = "app/static/uploads") -> dict:
    """
    Process image with YOLOv11-seg to detect coin and leaves,
    calculate real area in cm².
    
    Args:
        image_bytes: Raw image bytes from upload
        save_dir: Directory to save processed images
        
    Returns:
        dict with processing results
    """
    try:
        # Load model if not already loaded
        load_model()
        
        # Decode image from bytes
        image_array = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        
        if image is None:
            return {
                "success": False,
                "message": "Failed to decode image"
            }
        
        # Run YOLOv11 inference
        results = model(image)[0]
        
        if results.masks is None:
            return {
                "success": False,
                "message": "No objects detected (coin or leaf not found)"
            }
        
        # Extract classes and masks
        classes = results.boxes.cls.cpu().numpy().astype(int)
        names = results.names
        
        # Find Coin and Leaf indices
        coin_idx = -1
        leaf_idxs = []
        
        for i, cls in enumerate(classes):
            label = names[cls]
            if label == 'coin':
                if coin_idx == -1:  # Take first coin detected
                    coin_idx = i
            elif label == 'leaf':
                leaf_idxs.append(i)
        
        # Check if coin detected
        coin_detected = coin_idx != -1
        
        if not coin_detected:
            # Generate annotated image without calibration
            annotated_img = results.plot()
            cv2.putText(
                annotated_img,
                "Reference Coin Not Detected - Cannot Calculate Area",
                (50, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )
            
            # Save images with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            original_path = f"uploads/{timestamp}_original.jpg"
            segmented_path = f"uploads/{timestamp}_segmented.jpg"
            
            Path(save_dir).mkdir(parents=True, exist_ok=True)
            cv2.imwrite(f"{save_dir.rstrip('/')}/{timestamp}_original.jpg", image)
            cv2.imwrite(f"{save_dir.rstrip('/')}/{timestamp}_segmented.jpg", annotated_img)
            
            return {
                "success": False,
                "message": "Coin not detected - calibration required",
                "coin_detected": False,
                "image_paths": {
                    "original": original_path,
                    "segmented": segmented_path
                }
            }
        
        # Calculate coin area using shoelace formula
        coin_poly = results.masks.xy[coin_idx]
        coin_pixel_area = calculate_polygon_area(coin_poly)
        
        # Calculate scale factor (mm²/pixel)
        scale_factor = COIN_TRUE_AREA_MM2 / coin_pixel_area
        
        print(f"🪙 Coin detected. Pixel Area: {coin_pixel_area:.2f}, Scale: {scale_factor:.6f} mm²/px")
        
        # Calculate leaf areas
        total_leaf_area_mm2 = 0
        leaf_details = []
        
        for i, leaf_idx in enumerate(leaf_idxs):
            leaf_poly = results.masks.xy[leaf_idx]
            leaf_pixel_area = calculate_polygon_area(leaf_poly)
            
            # Convert to real area (mm²)
            real_area_mm2 = leaf_pixel_area * scale_factor
            total_leaf_area_mm2 += real_area_mm2
            
            leaf_details.append({
                "index": i + 1,
                "pixel_area": float(leaf_pixel_area),
                "real_area_mm2": float(real_area_mm2),
                "real_area_cm2": float(real_area_mm2 / 100)  # Convert to cm²
            })
            
            print(f"🍃 Leaf {i+1}: Pixel Area: {leaf_pixel_area:.2f}, Real Area: {real_area_mm2:.2f} mm²")
        
        # Convert total area to cm²
        total_leaf_area_cm2 = total_leaf_area_mm2 / 100
        
        # Generate annotated image
        annotated_img = results.plot()
        
        # Add text overlays
        text = f"Total Leaf Area: {total_leaf_area_cm2:.2f} cm^2 ({total_leaf_area_mm2:.1f} mm^2)"
        cv2.putText(annotated_img, text, (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        
        coin_text = f"Coin Ref: {COIN_TRUE_AREA_MM2:.1f} mm^2 ({COIN_DIAMETER_MM}mm)"
        cv2.putText(annotated_img, coin_text, (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        
        leaves_text = f"Leaves Detected: {len(leaf_idxs)}"
        cv2.putText(annotated_img, leaves_text, (30, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
        
        # Save images with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        original_path = f"uploads/{timestamp}_original.jpg"
        segmented_path = f"uploads/{timestamp}_segmented.jpg"
        
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        cv2.imwrite(f"{save_dir.rstrip('/')}/{timestamp}_original.jpg", image)
        cv2.imwrite(f"{save_dir.rstrip('/')}/{timestamp}_segmented.jpg", annotated_img)
        
        # Calculate leaf constant c (if needed)
        # For now, using simple average approach
        # c = A / (H × W) where H, W are bounding box dimensions
        leaf_constant = None
        if len(leaf_idxs) > 0:
            # Get average bounding box dimensions
            total_h = 0
            total_w = 0
            for leaf_idx in leaf_idxs:
                box = results.boxes.xywh[leaf_idx].cpu().numpy()
                total_w += box[2]  # width
                total_h += box[3]  # height
            
            avg_h = total_h / len(leaf_idxs)
            avg_w = total_w / len(leaf_idxs)
            
            # Calculate constant in cm units
            # Convert pixel dimensions to cm
            pixel_to_cm = np.sqrt(scale_factor / 100)  # approximate linear scale
            avg_h_cm = avg_h * pixel_to_cm
            avg_w_cm = avg_w * pixel_to_cm
            
            if avg_h_cm > 0 and avg_w_cm > 0:
                leaf_constant = total_leaf_area_cm2 / (avg_h_cm * avg_w_cm)
        
        return {
            "success": True,
            "total_leaf_area_cm2": float(total_leaf_area_cm2),
            "total_leaf_area_mm2": float(total_leaf_area_mm2),
            "leaf_constant": float(leaf_constant) if leaf_constant else None,
            "coin_detected": True,
            "num_leaves": len(leaf_idxs),
            "image_paths": {
                "original": original_path,
                "segmented": segmented_path
            },
            "metadata": {
                "coin_type": "500 IDR",
                "coin_diameter_mm": COIN_DIAMETER_MM,
                "coin_pixel_area": float(coin_pixel_area),
                "scale_factor_mm2_per_px": float(scale_factor),
                "leaf_details": leaf_details,
                "model": "YOLOv11n-seg",
                "timestamp": timestamp
            }
        }
        
    except Exception as e:
        print(f"❌ Error processing image: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            "success": False,
            "message": f"Processing error: {str(e)}"
        }


# Pre-load model on module import
load_model()
