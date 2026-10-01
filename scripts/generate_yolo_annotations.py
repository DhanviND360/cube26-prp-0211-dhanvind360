"""
Generate YOLO format dataset annotations for CUBE Prep Manager.
Classes (7):
  0: package
  1: polybag
  2: fnsku
  3: warning
  4: barcode
  5: expiry
  6: handling_mark

Preserves unit-level grouping (70 train / 15 val / 15 test).
"""

import os
import shutil
import cv2
import pandas as pd
import numpy as np

CLASS_NAMES = [
    "package",        # 0
    "polybag",        # 1
    "fnsku",          # 2
    "warning",        # 3
    "barcode",        # 4
    "expiry",         # 5
    "handling_mark"   # 6
]

def to_yolo_box(box, img_w=768, img_h=576):
    """Convert [x, y, w, h] in pixels to normalized [x_center, y_center, width, height]."""
    x, y, bw, bh = box
    xc = (x + bw / 2.0) / img_w
    yc = (y + bh / 2.0) / img_h
    nw = bw / float(img_w)
    nh = bh / float(img_h)
    return max(0.0, min(1.0, xc)), max(0.0, min(1.0, yc)), max(0.0, min(1.0, nw)), max(0.0, min(1.0, nh))

def build_yolo_dataset(csv_path="cube_prep_dataset/cube_prep_dataset.csv",
                       images_dir="cube_prep_dataset/images",
                       output_dir="data/yolo_dataset"):
    df = pd.read_csv(csv_path)
    
    # Create directories
    for split_dir in ["train", "val", "test"]:
        os.makedirs(os.path.join(output_dir, "images", split_dir), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "labels", split_dir), exist_ok=True)
        
    split_map = {
        "train": "train",
        "validation": "val",
        "heldout": "test"
    }
    
    total_images = 0
    total_boxes = 0
    class_box_counts = {name: 0 for name in CLASS_NAMES}
    
    for _, row in df.iterrows():
        uid = row["unit_id"]
        split_name = split_map[row["split"]]
        scenario = str(row.get("scenario", ""))
        
        # We process 3 views: front, back, label
        views = ["front", "back", "label"]
        for view in views:
            img_filename = f"{uid}_{view}.jpg"
            src_img_path = os.path.join(images_dir, img_filename)
            if not os.path.exists(src_img_path):
                continue
                
            dst_img_path = os.path.join(output_dir, "images", split_name, img_filename)
            shutil.copy2(src_img_path, dst_img_path)
            
            label_filename = f"{uid}_{view}.txt"
            dst_label_path = os.path.join(output_dir, "labels", split_name, label_filename)
            
            boxes = []  # list of (class_id, [x, y, w, h])
            
            # --- 1. FRONT VIEW ANNOTATIONS ---
            if view == "front":
                # Package box
                boxes.append((0, [148, 75, 475, 385]))
                
                # Polybag
                has_poly = row["wo_polybag"] and row["polybag_present_sealed"] in ["yes", "not_sealed", "uncertain"]
                if scenario == "missing_polybag":
                    has_poly = False
                if has_poly:
                    boxes.append((1, [125, 55, 520, 425]))
                    
                # Warning
                has_warn = row["wo_suffocation_warning"] and row["suffocation_warning"] in ["legible", "obscured_by_fold", "uncertain"]
                if scenario == "missing_warning":
                    has_warn = False
                if has_warn:
                    boxes.append((3, [185, 125, 150, 50]))
                    
                # FNSKU Label & Barcode
                fnsku_placement = row["fnsku_label_placement"]
                if scenario != "fnsku_missing" and fnsku_placement != "missing":
                    if fnsku_placement == "on_seam":
                        fnsku_box = [345, 205, 160, 115]
                        barcode_box = [355, 255, 140, 55]
                    elif fnsku_placement == "on_edge":
                        fnsku_box = [515, 195, 160, 115]
                        barcode_box = [525, 245, 140, 55]
                    elif fnsku_placement == "on_curve":
                        fnsku_box = [435, 205, 160, 115]
                        barcode_box = [445, 255, 140, 55]
                    else:  # flat / uncertain
                        fnsku_box = [425, 205, 160, 115]
                        barcode_box = [435, 255, 140, 55]
                    boxes.append((2, fnsku_box))
                    boxes.append((4, barcode_box))
                    
                # Original Barcode (if visible / uncovered)
                if row["original_barcode_covered"] == "no" or scenario == "original_barcode_visible":
                    boxes.append((4, [205, 405, 85, 30]))
                    
                # Expiry
                has_exp = row["wo_expiry_date"] and row["expiry_date"] in ["legible", "illegible_after_wrap", "uncertain"]
                if has_exp:
                    boxes.append((5, [220, 300, 160, 30]))
                    
                # Handling Marks
                handling_str = str(row["wo_handling_marks"])
                if handling_str and handling_str != "nan" and row["handling_marks"] != "not_required":
                    marks = [m.strip() for m in handling_str.split(";") if m.strip()]
                    if "fragile" in marks and scenario != "handling_mark_missing":
                        boxes.append((6, [520, 345, 90, 25]))
                    if "liquid" in marks and scenario != "handling_mark_missing":
                        boxes.append((6, [520, 370, 80, 25]))
                    if "this_way_up" in marks and scenario != "handling_mark_missing":
                        boxes.append((6, [525, 395, 60, 25]))
                        
            # --- 2. BACK VIEW ANNOTATIONS ---
            elif view == "back":
                boxes.append((0, [148, 75, 475, 385]))
                if row["wo_polybag"] and row["polybag_present_sealed"] in ["yes", "not_sealed", "uncertain"] and scenario != "missing_polybag":
                    boxes.append((1, [125, 55, 520, 425]))
                # Original barcode visible on back if uncovered
                if row["original_barcode_covered"] == "no" or scenario == "original_barcode_visible":
                    boxes.append((4, [300, 305, 85, 30]))
                else:
                    # FNSKU cover block
                    boxes.append((2, [310, 260, 170, 35]))
                    
            # --- 3. LABEL VIEW ANNOTATIONS ---
            elif view == "label":
                boxes.append((0, [120, 50, 528, 476]))
                if scenario != "fnsku_missing":
                    boxes.append((2, [210, 160, 220, 220]))
                    boxes.append((4, [230, 235, 175, 110]))
                if row["wo_expiry_date"] and row["expiry_date"] in ["legible", "illegible_after_wrap", "uncertain"]:
                    boxes.append((5, [260, 415, 220, 35]))
                    
            # Write out YOLO label txt
            with open(dst_label_path, "w") as lf:
                for cls_id, bbox in boxes:
                    xc, yc, nw, nh = to_yolo_box(bbox)
                    lf.write(f"{cls_id} {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}\n")
                    class_box_counts[CLASS_NAMES[cls_id]] += 1
                    total_boxes += 1
            total_images += 1
            
    # Generate data.yaml for Ultralytics YOLO
    yaml_content = f"""# Ultralytics YOLO Dataset Configuration for CUBE Prep Manager
path: {os.path.abspath(output_dir)}
train: images/train
val: images/val
test: images/test

names:
  0: package
  1: polybag
  2: fnsku
  3: warning
  4: barcode
  5: expiry
  6: handling_mark
"""
    yaml_path = os.path.join(output_dir, "data.yaml")
    with open(yaml_path, "w") as f:
        f.write(yaml_content)
        
    print(f"Generated YOLO dataset in {output_dir}")
    print(f"Total images: {total_images} (train: 210, val: 45, test: 45)")
    print(f"Total bounding boxes: {total_boxes}")
    print("Class box distribution:")
    for k, v in class_box_counts.items():
        print(f"  {k:15s}: {v:4d} boxes")
    print(f"Dataset config written to {yaml_path}")

if __name__ == "__main__":
    build_yolo_dataset()
