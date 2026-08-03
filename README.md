<h1 align="center">vapoursynth-letterbox</h1>

A VapourSynth plugin to find and mask letterbox.  

### Introduction

We understand letterbox as two parts.  

First, there is **permanent letterbox**.  
For example, a production may deliver a 1920x824 video in a 1920x1080 format. There is nothing but noise in the 128-pixel space on the top and bottom.  

In rare cases, while a production maintains a true letterbox for most of the video, occasionally they actually let some objects on the screen to go over to the outside space for effect. An example is the the opening of 173295 / 57810.  
This situation is natively supposed by this plugin. We always set a colour threshold for the permanent letterbox. Pixels outside this colour threshold will be protected.  

A pixel in the permanent letterbox is counted into the mask as long as it is within the thresholds.  

Second, there is **dynamic letterbox**.  
Sometimes a production will change the letterbox height per cut or even per frame to achieve special effect.  
This plugin has full support for dynamic letterbox.  

A pixel outside the permanent letterbox is only counted into the dynamic letterbox mask if the whole row of pixels is all within the thresholds.  

### Usage

You should use the Python wrapper to use this plugin. The Python wrapper has some very important pre and postprocessing. Only with these protection is this letterbox masking safe to use.  

The Python wrapper depends on vs-jetpack. Specifically `remove_grain`, `Morpho`, and `akarin.Expr`. If you can't use vs-jetpack, it's highly suggested to copy [the code](vsletterbox.py) in the wrapper out and implement it into your environment.  

The Python wrapper provides 2 functions:  
* `letterbox_mask`  
* `clean_letterbox`  

For video with no permanent letterbox:  
```py
from vsletterbox import letterbox_mask

letterbox_mask = letterbox_mask(clip)
clip = core.std.MaskedMerge(clip, clip.std.BlankClip(), letterbox_mask)
```

This is the same as:  
```py
from vsletterbox import clean_letterbox

clip = clean_letterbox(clip)
```

For the input to `letterbox_mask`, both GRAY clips and YUV clips are supported.  
The mask are built based on the Y plane even if you give it a YUV clip.  

For video with 128-pixel permanent letterbox:  
```py
[letterbox_mask|clean_letterbox](clip, permanent=[128, 128]) # [Top, Bottom]
```

As explained in the [introduction](#introduction), we use a colour threshold to detect the letterbox.  
For the threshold, by default the wrapper uses `[0 ~ 19]` (8-bit) if you give it an integer based clip, and `[0 ~ 0.075]` if you give it a float based clip. To adjust it:    
```py
[letterbox_mask|clean_letterbox](clip, high_thr=0.08)
[letterbox_mask|clean_letterbox](clip, high_thr=20*256)
```

Additionally, we also provide border deringing based on dynamic letterbox.  
This feature requires [bore](https://github.com/OpusGang/bore).  

```py
clean_letterbox(clip, bore_ythickness=[4, 4], bore_uthickness=[2, 2], bore_vthickness=[2, 2])
```

Full reference:  
```py
letterbox_mask(
    clip:            vs.VideoNode,

    low_thr:         float | int = 0,
    high_thr:        float | int = 0.075 | 19 | 4845,

    permanent:       list[int]   = [0, 0], # [Top, Bottom]
    permanent_str:   float       = 1.0,

    dynamic:         bool        = True,
    dynamic_ref:     Callable[[vs.VideoNode], vs.VideoNode] | None
                                 = None,
    dynamic_ref_thr: float       = 0.75,
    dynamic_str:     float       = 1.0,

    # We don't want to eliminate the noise in a pure black screen.  
    # 
    # First, the video is still going and it shouldn't just be completely blank and static.  
    # Furthermore, there are situations such as fading. When the video is fading to black, there
    # is noise during the fading. But when the fading ends, without a protection, the dynamic
    # letterbox will trigger, and suddenly all the noise goes away within the time of a single
    # frame. That'll also be odd.  
    #
    # With this protection, intially it will output dynamic letterbox at the strength of
    # `dynamic_str`. If the area of the dynamic letterbox expands past `fullblack_thr`, the
    # strength of the output mask will start to reduce linearly, until it reaches a full black
    # frame, where the strength will be `fullblack_str`.  
    fullblack_thr:   float       = 2/3,
    fullblack_str:   float       = 0.0,
)
```
```py
clean_letterbox(
    clip:            vs.VideoNode,

    low_thr:         float | int = 0,
    high_thr:        float | int = 0.075 | 19,

    permanent:       list[int]   = [0, 0], # [Top, Bottom]
    permanent_str:   float       = 1.0,
    permanent_color: list[int] | None # None uses the default of core.std.BlankClip
                                 = None,

    dynamic:         bool        = True,
    dynamic_ref:     Callable[[vs.VideoNode], vs.VideoNode] | None
                                 = None,
    dynamic_ref_thr: float       = 0.75,
    dynamic_str:     float       = 1.0, # None uses the default of core.std.BlankClip
    dynamic_color:   list[int] | None
                                 = None,

    fullblack_thr:   float       = 2/3,
    fullblack_str:   float       = 0.0,

    bore_ythickness: list[int] | None # [Top, Bottom]
                                 = None,
    bore_uthickness: list[int] | None # [Top, Bottom]
                                 = None,
    bore_vthickness: list[int] | None # [Top, Bottom]
                                 = None,
)
```
