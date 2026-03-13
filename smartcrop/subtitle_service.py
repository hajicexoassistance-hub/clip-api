# SubtitleService: generate ASS subtitle with style, animation, word timing
from style_presets import get_style
from animation_presets import get_animation

from style_presets import get_available_styles
from animation_presets import get_available_animations

def generate_ass(word_timings, options=None):
    """
    Generate ASS subtitle string with modular style and animation presets.
    options: dict with keys:
        - resolution: e.g. '1080x1920'
        - highlightColor: ASS color
        - stylePreset: style name (see get_available_styles())
        - customStyle: dict to override style fields
        - animationPreset: animation name (see get_available_animations())
        - wordsPerLine: int
        - rawText: fallback text
    """
    options = options or {}
    resolution = options.get('resolution', '1080x1920')
    resW, resH = resolution.split('x')
    highlight_color = options.get('highlightColor', '&H0000FFFF')
    style_preset = options.get('stylePreset', 'basic')
    custom_style = options.get('customStyle', {})
    animation_preset = options.get('animationPreset', 'flash')
    words_per_line = options.get('wordsPerLine', 4)
    raw_text = options.get('rawText', 'AI Video')

    style = get_style(style_preset, custom_style)
    # ASS Style Format
    style_line = f"Style: Default,{style['font']},{style['size']},{style['primary_color']},{style.get('secondary_color','&H000000FF')},{style['outline_color']},{style['back_color']},{style.get('bold',0)},{style.get('italic',0)},0,0,100,100,{style.get('spacing',0)},0,1,{style['outline']},{style.get('shadow',0)},{style['alignment']},40,40,{style['margin_v']},1"
    # Highlight style (simple: ganti warna utama)
    highlight_line = style_line.replace('Style: Default', 'Style: Highlight').replace(style['primary_color'], highlight_color)

    header = f"[Script Info]\nScriptType: v4.00+\nPlayResX: {resW}\nPlayResY: {resH}\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n{style_line}\n{highlight_line}\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"

    events = []
    if not word_timings:
        start_ts = "0:00:00.00"
        end_ts = "0:00:20.00"
        anim = get_animation(animation_preset)
        events.append(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{anim}{raw_text}")
    else:
        # Group words into lines
        lines = [word_timings[i:i+words_per_line] for i in range(0, len(word_timings), words_per_line)]
        for line in lines:
            start = line[0]['start']
            end = line[-1]['end']
            anim = get_animation(animation_preset)
            text = ' '.join([w['text'] for w in line])
            events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{anim}{text}")
    return header + '\n'.join(events)

def get_available_styles_list():
    return get_available_styles()

def get_available_animations_list():
    return get_available_animations()
