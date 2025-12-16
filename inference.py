import cv2
import numpy as np
from ultralytics import YOLO
import sys
import os

# Constants
COIN_DIAMETER_MM = 27.2 # Aluminum 500 IDR (Silver)
COIN_TRUE_AREA_MM2 = np.pi * ((COIN_DIAMETER_MM / 2) ** 2)

def calculate_area(masks, boxes, class_ids, img_shape):
    """
    Finds coin and leaf masks, calculates area.
    """
    coin_mask = None
    leaf_mask = None
    
    # Iterate through detections
    # We assume class 0 = coin, class 1 = leaf
    
    # Sort by potential criteria if multiple detections
    # For now, take the one with highest confidence or largest area?
    # Masks are usually ordered by confidence.
    
    coin_areas = []
    leaf_areas = []
    
    for i, class_id in enumerate(class_ids):
        mask = masks[i].data[0].cpu().numpy() # Extract mask
        # Resize mask to original image size if needed, but YOLO usually returns normalized or scaled
        # ultralytics masks.data are usually in model input size or output size (often smaller).
        # We need to resize to img_shape.
        
        # Actually masks.xy returns coordinates of polygon pixels in original image!
        # That is better for area calculation 'Polygon Area'.
        # But for pixel counting, bitmap key is useful.
        
        # Let's use the Polygon coordinates provided by ultralytics results[0].masks.xy
        pass

    return None

def run_inference(model_path, image_path, output_path):
    model = YOLO(model_path)
    
    image = cv2.imread(image_path)
    if image is None: 
        print(f"Error reading {image_path}")
        return

    results = model(image_path)[0]
    
    if results.masks is None:
        print("No masks detected.")
        cv2.imwrite(output_path, image)
        return

    # Extract classes and masks
    classes = results.boxes.cls.cpu().numpy().astype(int)
    names = results.names
    
    # Find Coin (class 0 or name 'coin') and Leaf (class 1 or name 'leaf')
    # Use names to be safe if ids shifted
    
    coin_idx = -1
    leaf_idxs = []
    
    for i, cls in enumerate(classes):
        label = names[cls]
        if label == 'coin':
            # If multiple coins, maybe take best confidence?
            if coin_idx == -1: coin_idx = i
        elif label == 'leaf':
            leaf_idxs.append(i)
            
    # Visualize
    annotated_img = results.plot()
    
    if coin_idx != -1:
        # Get coin mask area
        # Using polygon area (shootlace formula) from .xy
        coin_poly = results.masks.xy[coin_idx]
        # Shoelace formula for area
        coin_pixel_area = 0.5 * np.abs(np.dot(coin_poly[:, 0], np.roll(coin_poly[:, 1], 1)) - 
                                       np.dot(coin_poly[:, 1], np.roll(coin_poly[:, 0], 1)))
        
        scale_factor = COIN_TRUE_AREA_MM2 / coin_pixel_area
        
        print(f"Coin detected. Pixel Area: {coin_pixel_area:.2f}, Scale: {scale_factor:.6f} mm^2/px")
        
        total_leaf_area = 0
        for i in leaf_idxs:
            leaf_poly = results.masks.xy[i]
            leaf_pixel_area = 0.5 * np.abs(np.dot(leaf_poly[:, 0], np.roll(leaf_poly[:, 1], 1)) - 
                                           np.dot(leaf_poly[:, 1], np.roll(leaf_poly[:, 0], 1)))
            
            real_area = leaf_pixel_area * scale_factor
            total_leaf_area += real_area
            print(f"Leaf detected. Pixel Area: {leaf_pixel_area:.2f}, Real Area: {real_area:.2f} mm^2")
            
        # Draw Text on Image
        text = f"Total Leaf Area: {total_leaf_area:.2f} mm^2"
        cv2.putText(annotated_img, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.putText(annotated_img, f"Coin Ref: {COIN_TRUE_AREA_MM2:.1f} mm^2", (50, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

    else:
        print("Coin not detected! Cannot calculate real area.")
        cv2.putText(annotated_img, "Reference Coin Not Detected", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    cv2.imwrite(output_path, annotated_img)
    print(f"Saved inference result to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python inference.py <model_path> <image_path> [output_path]")
    else:
        model_p = sys.argv[1]
        img_p = sys.argv[2]
        out_p = sys.argv[3] if len(sys.argv) > 3 else "output_inference.jpg"
        run_inference(model_p, img_p, out_p)
