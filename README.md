# Orbbec Femto Bolt — Python Development Environment Setup

> **Part 1** of the Robotic Canopy Digital Twin Tracking System  
> Overhead RGBD marker tracking for origami robot co-design workshops

---

## Overview

This guide walks through setting up a Python development environment for the **Orbbec Femto Bolt** depth camera on Windows. By the end, you will have a working pipeline that captures synchronized RGB (1920×1080) and Depth (640×576) streams from the Femto Bolt using the Orbbec SDK v2 Python Wrapper.

### Hardware

| Component | Specification |
|-----------|--------------|
| Camera | Orbbec Femto Bolt (iToF, Microsoft co-developed) |
| Depth Sensor | 1MP ToF, 120° WFOV / 75×65° NFOV |
| Depth Range | 0.25–5.46 m (mode-dependent) |
| RGB Camera | 4K (3840×2160) with HDR, 80×51° FOV |
| Interface | USB-C 3.2 Gen 1 (power + data) |
| Accuracy | Systematic error < 11 mm + 0.1% distance |

### Software Stack

| Package | Version | Purpose |
|---------|---------|---------|
| Python | 3.8–3.13 | Runtime |
| pyorbbecsdk2 | ≥ 2.0.15 | Orbbec SDK v2 Python bindings |
| opencv-python | ≥ 4.x | Image processing, HSV detection, visualization |
| numpy | ≥ 1.24 | Array operations |
| scipy | ≥ 1.10 | Hungarian algorithm for multi-marker tracking |
| Pillow | ≥ 10.0 | GIF export |

---

## Prerequisites

- **OS**: Windows 10/11 (64-bit)
- **Python**: 3.8–3.13 installed and available in PATH ([download](https://www.python.org/downloads/))
- **Editor**: VS Code recommended (with [Python extension](https://marketplace.visualstudio.com/items?itemName=ms-python.python))
- **Hardware**: Orbbec Femto Bolt connected via USB 3.0 port
- **Verification**: Camera streams confirmed working in [Orbbec Viewer](https://github.com/orbbec/OrbbecSDK_v2/releases)

---

## Step 1: Register Windows Metadata (One-Time)

Windows requires UVC device metadata registration for proper frame timestamps and synchronization. **Skip this step if you have already registered via Orbbec Viewer installer.**

### 1.1 Download the Registration Script

Clone the pyorbbecsdk repository (or download just the script):

```bash
git clone https://github.com/orbbec/pyorbbecsdk.git
```

The script is located at `pyorbbecsdk/scripts/env_setup/obsensor_metadata_win10.ps1`.

### 1.2 Run the Script

> **Important**: The Femto Bolt must be connected and powered on.

Open **PowerShell as Administrator** and run:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\path\to\pyorbbecsdk\scripts\env_setup\obsensor_metadata_win10.ps1" -op install_all
```

> **Note**: Replace `C:\path\to\` with the actual path to your cloned repository.  
> If your path contains spaces, wrap the entire `-File` argument in double quotes.

Expected output:

```
2 connected Orbbec devices were found:
...
Task Completed
```

If you see `skipping - metadata key already exists`, the registration was already done — this is fine.

### Troubleshooting

| Issue | Solution |
|-------|----------|
| `UnauthorizedAccess` / script cannot be loaded | Use the `powershell -ExecutionPolicy Bypass -File ...` syntax shown above |
| Path with spaces causes `Set-Location` error | Wrap the full path in double quotes |
| `CommandNotFoundException` | Ensure you `cd` into the correct directory first, or use the full `-File` path |

---

## Step 2: Create Project Environment

### 2.1 Create Project Directory

```bash
mkdir C:\Projects\canopy-tracker
cd C:\Projects\canopy-tracker
```

### 2.2 Create and Activate Virtual Environment

```bash
python -m venv venv
.\venv\Scripts\activate
```

> You should see `(venv)` prefix in your terminal prompt after activation.  
> Re-activate each time you open a new terminal session.

### 2.3 VS Code Integration (Optional)

1. Open the project folder: **File → Open Folder → `C:\Projects\canopy-tracker`**
2. Press `Ctrl+Shift+P` → **Python: Select Interpreter**
3. Choose `.\venv\Scripts\python.exe`

---

## Step 3: Install Dependencies

With the virtual environment activated:

```bash
pip install pyorbbecsdk2 opencv-python numpy scipy Pillow
```

### Verify Installation

```bash
python -c "from pyorbbecsdk import *; import cv2; import numpy; import scipy; from PIL import Image; print('All dependencies OK')"
```

> **Important**: The pip package is named `pyorbbecsdk2`, but the Python import is `pyorbbecsdk`.  
> This is by design — not a bug.

### Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'pyorbbecsdk'` | Ensure virtual environment is activated (`(venv)` prefix visible) |
| `ImportError: DLL load failed` | Install [Visual C++ Redistributable 2019+](https://aka.ms/vs/17/release/vc_redist.x64.exe) |
| `pip` not found | Use `python -m pip install ...` instead |

---

## Step 4: Verify Camera Connection

Save the following script as `test_femtobolt.py` and run it with the Femto Bolt connected.

> **Close Orbbec Viewer first** — the camera can only be accessed by one application at a time.

```bash
python test_femtobolt.py
```

<details>
<summary><strong>test_femtobolt.py</strong> (click to expand)</summary>

```python
"""
Femto Bolt Connection Test
Confirms pyorbbecsdk2 can connect to the camera and capture RGB + Depth frames.
Press 'q' to quit the preview window.
"""

from pyorbbecsdk import *
import numpy as np
import cv2
import sys


def main():
    # --- 1. Detect device ---
    ctx = Context()
    device_list = ctx.query_devices()
    device_count = device_list.get_count()

    if device_count == 0:
        print("[ERROR] No Orbbec device detected.")
        print("  - Is the USB cable connected?")
        print("  - Are you using a USB 3.0 port?")
        print("  - Is Orbbec Viewer closed?")
        sys.exit(1)

    print(f"[OK] {device_count} device(s) detected")

    # --- 2. Open device ---
    device = device_list.get_device_by_index(0)
    device_info = device.get_device_info()
    print(f"  Device : {device_info.get_name()}")
    print(f"  Serial : {device_info.get_serial_number()}")
    print(f"  FW     : {device_info.get_firmware_version()}")

    # --- 3. Configure pipeline ---
    pipeline = Pipeline(device)
    config = Config()

    # Color stream: 1920x1080 @ 30fps MJPG
    color_profiles = pipeline.get_stream_profile_list(OBSensorType.COLOR_SENSOR)
    color_profile = None
    for i in range(color_profiles.get_count()):
        profile = color_profiles.get_video_stream_profile(i)
        if (profile.get_width() == 1920 and
            profile.get_height() == 1080 and
            profile.get_fps() == 30 and
            profile.get_format() == OBFormat.MJPG):
            color_profile = profile
            break

    if color_profile is None:
        color_profile = color_profiles.get_default_video_stream_profile()
        print(f"  [WARN] Using default color profile: "
              f"{color_profile.get_width()}x{color_profile.get_height()}"
              f"@{color_profile.get_fps()}fps")
    else:
        print(f"  [OK] Color : 1920x1080 @ 30fps (MJPG)")

    config.enable_stream(color_profile)

    # Depth stream: NFOV Unbinned 640x576 @ 30fps
    depth_profiles = pipeline.get_stream_profile_list(OBSensorType.DEPTH_SENSOR)
    depth_profile = None
    for i in range(depth_profiles.get_count()):
        profile = depth_profiles.get_video_stream_profile(i)
        if (profile.get_width() == 640 and
            profile.get_height() == 576 and
            profile.get_fps() == 30):
            depth_profile = profile
            break

    if depth_profile is None:
        depth_profile = depth_profiles.get_default_video_stream_profile()
        print(f"  [WARN] Using default depth profile: "
              f"{depth_profile.get_width()}x{depth_profile.get_height()}"
              f"@{depth_profile.get_fps()}fps")
    else:
        print(f"  [OK] Depth : 640x576 @ 30fps (NFOV)")

    config.enable_stream(depth_profile)

    # Note: D2C alignment is configured in the full tracker, not here.

    # --- 4. Start pipeline ---
    pipeline.start(config)
    print("\nCamera started. Press 'q' to quit.\n")

    frame_count = 0

    try:
        while True:
            frames = pipeline.wait_for_frames(1000)
            if frames is None:
                continue

            color_frame = frames.get_color_frame()
            depth_frame = frames.get_depth_frame()

            if color_frame is None or depth_frame is None:
                continue

            frame_count += 1

            # Decode color frame
            color_data = np.frombuffer(color_frame.get_data(), dtype=np.uint8)
            if color_frame.get_format() == OBFormat.MJPG:
                color_image = cv2.imdecode(color_data, cv2.IMREAD_COLOR)
            elif color_frame.get_format() == OBFormat.RGB:
                color_image = color_data.reshape(
                    (color_frame.get_height(), color_frame.get_width(), 3))
                color_image = cv2.cvtColor(color_image, cv2.COLOR_RGB2BGR)
            elif color_frame.get_format() == OBFormat.BGRA:
                color_image = color_data.reshape(
                    (color_frame.get_height(), color_frame.get_width(), 4))
                color_image = cv2.cvtColor(color_image, cv2.COLOR_BGRA2BGR)
            else:
                color_image = color_data.reshape(
                    (color_frame.get_height(), color_frame.get_width(), 3))

            if color_image is None:
                continue

            # Decode depth frame
            depth_data = np.frombuffer(depth_frame.get_data(), dtype=np.uint16)
            depth_image = depth_data.reshape(
                (depth_frame.get_height(), depth_frame.get_width()))

            # Depth visualization
            depth_vis = cv2.normalize(depth_image, None, 0, 255,
                                      cv2.NORM_MINMAX, dtype=cv2.CV_8U)
            depth_colormap = cv2.applyColorMap(depth_vis, cv2.COLORMAP_JET)

            # Overlay info
            h, w = color_image.shape[:2]
            info_text = (f"Frame #{frame_count} | "
                         f"Color: {w}x{h} | "
                         f"Depth: {depth_frame.get_width()}x"
                         f"{depth_frame.get_height()}")
            cv2.putText(color_image, info_text, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            cx, cy = depth_image.shape[1] // 2, depth_image.shape[0] // 2
            center_depth = depth_image[cy, cx]
            cv2.putText(color_image, f"Center depth: {center_depth} mm",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (0, 255, 255), 2)

            # Display
            preview_color = cv2.resize(color_image, (960, 540))
            preview_depth = cv2.resize(depth_colormap, (480, 270))

            cv2.imshow("Femto Bolt - Color", preview_color)
            cv2.imshow("Femto Bolt - Depth", preview_depth)

            if frame_count == 1:
                print(f"  First frame captured.")
                print(f"    Color : {w}x{h} ({color_frame.get_format()})")
                print(f"    Depth : {depth_frame.get_width()}x"
                      f"{depth_frame.get_height()}")
                print(f"    Center: {center_depth} mm")

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        pipeline.stop()
        cv2.destroyAllWindows()
        print(f"\nTest complete. {frame_count} frames captured.")


if __name__ == "__main__":
    main()
```

</details>

### Expected Output

```
[OK] 1 device(s) detected
  Device : Orbbec Femto Bolt
  Serial : XXXXXXXXXXXX
  FW     : 1.0.9
  [OK] Color : 1920x1080 @ 30fps (MJPG)
  [OK] Depth : 640x576 @ 30fps (NFOV)

Camera started. Press 'q' to quit.

  First frame captured.
    Color : 1920x1080 (OBFormat.MJPG)
    Depth : 640x576
    Center: 589 mm

Test complete. 2800 frames captured.
```

Two windows should appear: a color preview and a depth heatmap. Press `q` to exit.

### Known Benign Warnings

| Warning | Cause | Impact |
|---------|-------|--------|
| `Center depth: 0 mm` on first frame | Depth sensor warming up | None — resolves after 1–2 frames |
| `libpng warning: iCCP: known incorrect sRGB profile` | OpenCV PNG color profile mismatch | None — purely cosmetic |

---

## Quick Reference

Full setup from scratch in one terminal session:

```powershell
# === One-time: Register Windows metadata (Admin PowerShell) ===
powershell -ExecutionPolicy Bypass -File "C:\path\to\pyorbbecsdk\scripts\env_setup\obsensor_metadata_win10.ps1" -op install_all

# === Project setup ===
mkdir C:\Projects\canopy-tracker
cd C:\Projects\canopy-tracker
python -m venv venv
.\venv\Scripts\activate
pip install pyorbbecsdk2 opencv-python numpy scipy Pillow

# === Verify ===
python -c "from pyorbbecsdk import *; print('OK')"
python test_femtobolt.py
```

---

## Resources

| Resource | Link |
|----------|------|
| pyorbbecsdk GitHub | https://github.com/orbbec/pyorbbecsdk |
| SDK v2 Python Docs | https://orbbec.github.io/pyorbbecsdk/ |
| PyPI Package | https://pypi.org/project/pyorbbecsdk2/ |
| Femto Bolt Hardware Specs | https://www.orbbec.com/documentation/femto-bolt-hardware-specifications/ |
| Femto Bolt vs Azure Kinect | https://www.orbbec.com/documentation/comparison-with-azure-kinect-dk/ |
| Orbbec SDK v2 Repo | https://github.com/orbbec/OrbbecSDK_v2 |

---

## Next Steps

Once the test script confirms camera operation, proceed to **Part 2**: Multi-Color Fluorescent Marker Tracker — a real-time 8-point tracking system using 4-color HSV detection with color-constrained Hungarian matching for robust ID assignment.

---

## License

MIT

