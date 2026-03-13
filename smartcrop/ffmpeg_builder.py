"""
FFmpeg filter builder for scene-based cropping.
"""

from filter_presets import get_filter

def build_filter(scene_data, height, filter_name=None):
    if not scene_data:
        return ""
    filters = []
    grad_height = int(height * 0.20)
    height_str = str(height)
    grad_y = str(height - grad_height)
    crop_w = int(scene_data[0][3])
    for i, s in enumerate(scene_data):
        start, end, x, w = s
        # Video crop per scene
        chain = [
            f"[0:v]trim={start}:{end}",
            f"crop={w}:{height}:{x}:0"
        ]
        # Insert filter preset if provided
        if filter_name:
            preset = get_filter(filter_name)
            if preset:
                chain.append(preset)
        chain.append(f"setpts=PTS-STARTPTS[v{i}]")
        f = ",".join(chain)
        filters.append(f)
    # Gabungkan semua scene
    concat = "".join([f"[v{i}]" for i in range(len(scene_data))])
    filters.append(
        f"{concat}concat=n={len(scene_data)}:v=1:a=0[vcat]"
    )
    # Blur saja bagian bawah video (20%)
    filters.append(
        f"[vcat]crop={crop_w}:{height}:0:0,format=rgba[cropped];"
        f"[cropped]split=2[base][blur];"
        f"[blur]crop={crop_w}:{grad_height}:0:{grad_y},boxblur=10,format=rgba[blurred];"
        f"[base][blurred]overlay=0:{grad_y}:format=auto,format=yuv420p[outv]"
    )
    return ";".join(filters)
