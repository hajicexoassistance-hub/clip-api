"""
Crop calculation for portrait video.
"""
def calc_crop(center_x, width, height):
    crop_w = int(height * 9 / 16)
    x = int(center_x - crop_w / 2)
    if x < 0:
        x = 0
    if x + crop_w > width:
        x = width - crop_w
    return x, crop_w
