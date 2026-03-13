def slide_up(duration_ms=500, resolution="1080x1920"):
    w, h = map(int, resolution.split('x'))
    center_x = w // 2
    # Slide up to a higher position (around bottom 1/4)
    target_y = h - 300
    start_y = target_y + 50
    return f"{{\\fad(200,200)\\move({center_x},{start_y},{center_x},{target_y},0,300)}}"

def slide_up_bounce(duration_ms=500, resolution="1080x1920"):
    w, h = map(int, resolution.split('x'))
    center_x = w // 2
    target_y = h - 350
    start_y = target_y + 100
    return f"{{\\fad(200,200)\\move({center_x},{start_y},{center_x},{target_y},0,400)}}"

def zoom_in(duration_ms=500, resolution="1080x1920"):
    return "{\\fscx0\\fscy0\\t(0,300,\\fscx100\\fscy100)}"

def flash(duration_ms=500, resolution="1080x1920"):
    return "{\\t(0,100,\\1c&HFFFFFF&)\\t(100,200,\\1c&H00FFFF&)}"

ANIMATIONS = {
    "slide_up": slide_up,
    "slide_up_bounce": slide_up_bounce,
    "zoom_in": zoom_in,
    "flash": flash
}

def get_animation(name, **kwargs):
    return ANIMATIONS.get(name, lambda **k: "")(**kwargs)

def get_available_animations():
    return list(ANIMATIONS.keys())
