# Preset ASS subtitle styles ala StyleService adopt
STYLES = {
    "basic": {
        "font": "Oswald",
        "size": 100,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "back_color": "&H00000000",
        "bold": 1,
        "outline": 4,
        "alignment": 2,
        "margin_v": 150
    },
    "modern_bold": {
        "font": "Oswald",
        "size": 110,
        "primary_color": "&H0000FFFF",
        "outline_color": "&H00000000",
        "back_color": "&H00000000",
        "bold": 1,
        "outline": 4,
        "alignment": 2,
        "margin_v": 200
    },
    "aesthetic_light": {
        "font": "Montserrat",
        "size": 90,
        "primary_color": "&H00E0E0E0",
        "outline_color": "&H00333333",
        "back_color": "&H00000000",
        "bold": 0,
        "italic": 1,
        "outline": 2,
        "alignment": 2,
        "margin_v": 150
    },
    "gaming_neon": {
        "font": "Impact",
        "size": 120,
        "primary_color": "&H00FF00FF",
        "outline_color": "&H00000000",
        "back_color": "&H00000000",
        "bold": 1,
        "outline": 5,
        "alignment": 2,
        "margin_v": 250
    },
    "cinematic_serif": {
        "font": "DM Serif Text",
        "size": 100,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "back_color": "&H00000000",
        "bold": 0,
        "italic": 0,
        "outline": 2,
        "alignment": 2,
        "spacing": 2,
        "margin_v": 150
    }
}

def get_style(name, override=None):
    style = STYLES.get(name, STYLES["basic"]).copy()
    if override:
        style.update(override)
    return style

def get_available_styles():
    return list(STYLES.keys())
