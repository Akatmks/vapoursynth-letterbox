<h1 align="center">vapoursynth-letterbox</h1>

A VapourSynth plugin to find and clean letterbox.  

### Usage

You should use the Python wrapper to use this plugin. The Python wrapper has some very important pre and postprocessing. Only with these protection is this letterbox masking safe to use.  

The Python wrapper depends on vs-jetpack. If you can't use vs-jetpack, it's highly suggested to copy [the code](vsletterbox.py) in the wrapper out and implement it into your environment.  

For video with no permanent letterbox:  
```py
from vsletterbox import clean_letterbox

clip = clean_letterbox(clip)
```

For video with 129-pixel permanent letterbox:  
```py
clip = clean_letterbox(clip, permanent=[129, 129]) # [Top, Bottom]
```

In addition to cleaning the noise, we can also perform border deringing based on the dynamic letterbox detected.  
This feature requires [bore](https://github.com/OpusGang/bore).  
```py
clip = clean_letterbox(clip, permanent=[129, 129], bore_ythickness=[4, 4], bore_uthickness=[2, 2], bore_vthickness=[2, 2])
```

Alternatively, we also provide `letterbox_mask` function where you can apply your own cleaning.  

```py
from vsletterbox import letterbox_mask

mask = letterbox_mask(clip, permanent=[129, 129])
```

### Method

We detect letterbox based on three details:  
1. We iterate row by row from the edge pixel in, calculating the mean brightness of the pixels in each row.  
  We detect if starting from a certain row, this mean brightness rapidly increases, through a statistical moving predicter.  

2. We apply a sensitive general edgemask to the image, and this row must have high edgemask coverage.  
  This is to prevent cases such as title screens with only white text on black background to be detected as letterbox.  

3. We apply a hard brightness requirement where the next few image rows inside the border row must have.  
  This is to combat the case of intentional light bleeding (not talking about border ringing from scaling) in some special cases to be recognised as letterbox.  

4. If the detected row is within 2 rows from the user provided `permanent` row, we snap the detected row to the `permanent` row.  
  This is to combat the case where there is not a clean cutoff at the border and random pixels protrude to the otherside.  
  In addition, method 1. requires rapid change of brightness, and in very dark scenes, in case of dirty border, there might not be enough change to trigger the detection on the very first border row. This is also to combat this potential issue.  

5. When there is no letterbox detected such as in a pure black frame, or when the border is rejected by method 2. user provided `permanent` row applies.  

Once letterbox border is identified:  

6. Any pixel of the letterbox whose brightness is below a set threshold is cleaned to pure black.  
  This threshold is to protect cases where there are intential items in the border such as the opening of 173295 / 57810.  
  ⠀  
  This is protected by a `Morpho.closing()` to clean the few extreme pixels and a `Morpho.minimum()` to make the cleaning stay further away from intential items.  

7. We don't want to eliminate the noise in a pure black screen for multiple reasons.  
  ⠀  
  First, the video is still going and it shouldn't just be completely blank and static.  
  Second, there are situations such as fading. When the image is fading to black, there is noise during the fading. But when the fading ends, the letterbox detection triggers, and suddenly all the noise goes away within the time of a single frame. That'll be really odd.  
  ⠀  
  Instead a protection is applied and the letterbox cleaning strength is reduced as the area of the letterbox increases until it reaches a full black screen where no cleaning is applied.  
  ⠀  
  As an exception, the clearning will always apply in the user provided permanent letterbox in a pure black screen.  

8. `bore` will be applied to the image within the letterbox with the specified thickness.  

### Reference

```py
clean_letterbox(
    clip:            vs.VideoNode,

    # Threshold in method 6.
    # Default to around 19 at 8-bit
    thr:             float     = 0.075

    # Permanent letterbox used in method 4. and 5., as well as in method 7.
    permanent:       list[int] = [0, 0], # [Top, Bottom]

    # Enables the detection, without which only method 6. and 8. will apply  
    dynamic:         bool      = True,
    # Method 3.
    # Default to around 25 at 8-bit
    dynamic_thr:     float     = 0.1,
    # Method 2.
    dynamic_ref:     Callable[[vs.VideoNode], vs.VideoNode]
                               = ExKirsch().edgemask,
    # Method 2.
    dynamic_ref_thr: float     = 1/2,

    # Method 7.
    # The cleaning strength starts reducing when the area of the image is smaller than this
    # threshold.
    fullblack_thr:   float     = 1/3,

    # Method 8.
    bore_y:          list[int] = [0, 0], # [Top, Bottom]
    bore_u:          list[int] = [0, 0], # [Top, Bottom]
    bore_v:          list[int] = [0, 0], # [Top, Bottom]
)
```
```py
letterbox_mask(
    clip:            vs.VideoNode,

    # Method 1., 2., 3., 4., 5., and 7. applies

    # Permanent letterbox used in method 4. and 5., as well as in method 7.
    permanent:       list[int] = [0, 0], # [Top, Bottom]

    # Method 3.
    dynamic_thr:     float     = 0.1,
    # Method 2.
    dynamic_ref:     Callable[[vs.VideoNode], vs.VideoNode]
                               = ExKirsch().edgemask,
    # Method 2.
    dynamic_ref_thr: float     = 1/2,

    # Method 7.
    # The cleaning strength starts reducing when the area of the image is smaller than this
    # threshold.
    fullblack_thr:   float     = 1/3,
)
```
```py
find_letterbox(
    clip:            vs.VideoNode,

    # Method 1., 2., 3., 4., 5. applies
    # Outputs `VSLETTERBOX_TOP_ROW` and `VSLETTERBOX_BOTTOM_ROW` frame properties marking the first
    # and last row of the image, both inclusive (of the image)

    # Permanent letterbox used in method 4. and 5., as well as in method 7.
    permanent:       list[int] = [0, 0], # [Top, Bottom]

    # Method 3.
    dynamic_thr:     float     = 0.1,
    # Method 2.
    dynamic_ref:     Callable[[vs.VideoNode], vs.VideoNode]
                               = ExKirsch().edgemask,
    # Method 2.
    dynamic_ref_thr: float     = 1/2,
)
```
