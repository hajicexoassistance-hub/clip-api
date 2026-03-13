# Preset FFmpeg filters ala FilterService adopt
FILTERS = {
    "vignette": "vignette=PI/4",
    "sepia": "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131",
    "grayscale": "colorchannelmixer=.3:.4:.3:0:.3:.4:.3:0:.3:.4:.3",
    "dramatic": "curves=all='0/0 0.5/0.4 1/1',unsharp=5:5:1.0:5:5:0.0",
    "vintage": "curves=vintage,noise=alls=10:allf=t+u",
    "warm": "curves=all='0/0 0.5/0.55 1/1',hue=h=0:s=1.2:b=0",
    "cold": "curves=all='0/0 0.5/0.45 1/1',hue=h=0:s=0.8:b=0",
    "grain": "noise=alls=20:allf=t+u",
    "bright": "eq=brightness=0.1:contrast=1.1",
    "dark": "eq=brightness=-0.1:contrast=1.2",
    "hdr": "hqdn3d=1.5:1.5:6:6,unsharp=5:5:0.5:5:5:0.0"
}

def get_filter(name):
    return FILTERS.get(name.lower(), "")

def get_available_filters():
    return list(FILTERS.keys())
