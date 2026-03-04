"""
test_femtobolt.py — Orbbec Femto Bolt Connection Test
======================================================

Verifies that pyorbbecsdk2 can successfully connect to the Femto Bolt
and capture synchronized RGB + Depth frames.

Usage:
    python test_femtobolt.py

Controls:
    q — Quit and close preview windows

Prerequisites:
    - Femto Bolt connected via USB 3.0
    - Orbbec Viewer must be CLOSED (camera cannot be shared)
    - Windows metadata registered (see README.md Step 1)
    - Dependencies installed: pyorbbecsdk2, opencv-python, numpy

Note:
    The pip package is 'pyorbbecsdk2' but the import name is 'pyorbbecsdk'.
    This is intentional — not a bug.
"""

from pyorbbecsdk import *
import numpy as np
import cv2
import sys


def main():
    # ================================================================
    # 1. DEVICE DETECTION
    # ================================================================
    ctx = Context()
    device_list = ctx.query_devices()
    device_count = device_list.get_count()

    if device_count == 0:
        print("[ERROR] No Orbbec device detected.")
        print("  Checklist:")
        print("  - Is the USB cable securely connected?")
        print("  - Are you using a USB 3.0 port?")
        print("  - Is Orbbec Viewer closed? (cannot share camera)")
        sys.exit(1)

    print(f"[OK] {device_count} device(s) detected")

    # ================================================================
    # 2. OPEN DEVICE AND PRINT INFO
    # ================================================================
    device = device_list.get_device_by_index(0)
    device_info = device.get_device_info()
    print(f"  Device : {device_info.get_name()}")
    print(f"  Serial : {device_info.get_serial_number()}")
    print(f"  FW     : {device_info.get_firmware_version()}")

    # ================================================================
    # 3. CONFIGURE PIPELINE
    # ================================================================
    pipeline = Pipeline(device)
    config = Config()

    # --- Color stream: 1920x1080 @ 30fps (MJPG) ---
    # This resolution provides ~30-40 px diameter for 1-inch markers
    # at 2.75m overhead distance, sufficient for reliable detection.
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
        # Fall back to default if exact match not found
        color_profile = color_profiles.get_default_video_stream_profile()
        print(f"  [WARN] Using default color profile: "
              f"{color_profile.get_width()}x{color_profile.get_height()}"
              f"@{color_profile.get_fps()}fps")
    else:
        print(f"  [OK] Color : 1920x1080 @ 30fps (MJPG)")

    config.enable_stream(color_profile)

    # --- Depth stream: NFOV Unbinned 640x576 @ 30fps ---
    # NFOV mode: 75x65 deg FOV, effective range 0.5-3.86m
    # Suitable for overhead mounting at ~2.75m height.
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

    # D2C (Depth-to-Color) alignment is NOT enabled in this test script.
    # It will be configured in the full multi-color tracker using the
    # correct pyorbbecsdk2 v2 API.

    # ================================================================
    # 4. START PIPELINE AND CAPTURE LOOP
    # ================================================================
    pipeline.start(config)
    print("\nCamera started. Press 'q' to quit.\n")

    frame_count = 0

    try:
        while True:
            # Wait up to 1000ms for a synchronized frameset
            frames = pipeline.wait_for_frames(1000)
            if frames is None:
                continue

            color_frame = frames.get_color_frame()
            depth_frame = frames.get_depth_frame()

            if color_frame is None or depth_frame is None:
                continue

            frame_count += 1

            # --- Decode color frame ---
            # Femto Bolt typically outputs MJPG; decode to BGR for OpenCV.
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
                # Generic fallback: assume 3-channel
                color_image = color_data.reshape(
                    (color_frame.get_height(), color_frame.get_width(), 3))

            if color_image is None:
                continue

            # --- Decode depth frame ---
            # Depth data is uint16 in millimeters.
            depth_data = np.frombuffer(depth_frame.get_data(), dtype=np.uint16)
            depth_image = depth_data.reshape(
                (depth_frame.get_height(), depth_frame.get_width()))

            # Normalize to 0-255 and apply colormap for visualization
            depth_vis = cv2.normalize(depth_image, None, 0, 255,
                                      cv2.NORM_MINMAX, dtype=cv2.CV_8U)
            depth_colormap = cv2.applyColorMap(depth_vis, cv2.COLORMAP_JET)

            # --- Overlay status text ---
            h, w = color_image.shape[:2]
            info_text = (f"Frame #{frame_count} | "
                         f"Color: {w}x{h} | "
                         f"Depth: {depth_frame.get_width()}x"
                         f"{depth_frame.get_height()}")
            cv2.putText(color_image, info_text, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Sample and display depth at image center
            cx, cy = depth_image.shape[1] // 2, depth_image.shape[0] // 2
            center_depth = depth_image[cy, cx]
            cv2.putText(color_image, f"Center depth: {center_depth} mm",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (0, 255, 255), 2)

            # --- Display preview windows ---
            preview_color = cv2.resize(color_image, (960, 540))
            preview_depth = cv2.resize(depth_colormap, (480, 270))

            cv2.imshow("Femto Bolt - Color", preview_color)
            cv2.imshow("Femto Bolt - Depth", preview_depth)

            # Print first-frame diagnostic info
            if frame_count == 1:
                print(f"  First frame captured.")
                print(f"    Color : {w}x{h} ({color_frame.get_format()})")
                print(f"    Depth : {depth_frame.get_width()}x"
                      f"{depth_frame.get_height()}")
                print(f"    Center: {center_depth} mm")

            # Exit on 'q' key press
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        pipeline.stop()
        cv2.destroyAllWindows()
        print(f"\nTest complete. {frame_count} frames captured.")
        print(f"If you saw both color and depth windows, everything works!")
        print(f"Next step: run the multi-color marker tracker.")


if __name__ == "__main__":
    main()
