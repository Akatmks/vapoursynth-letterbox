# vapoursynth-letterbox
# Copyright (c) Akatsumekusa and contributors

# ---------------------------------------------------------------------
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# ---------------------------------------------------------------------

from vsexprtools import norm_expr
from functools import partial
from vskernels import Bilinear
from vsmasktools import ExKirsch, Morpho
from vstools import ChromaLocation, ColorRange, core, get_y, join, split, vs

def find_letterbox(
        clip,
        permanent=[0, 0],
        dynamic_ref=ExKirsch().edgemask,
        dynamic_ref_thr=2/3
    ):
    assert permanent[0] >= 0
    assert permanent[1] >= 0
    assert permanent[0] + permanent[1] < clip.height - 4
    permanent_top_row = permanent[0]
    permanent_bottom_row = clip.height - 1 - permanent[1]
    assert dynamic_ref_thr >= 0.0 and dynamic_ref_thr <= 1.0

    assert clip.format.num_planes in [1, 3]
    if clip.format.num_planes == 3:
        pre = Bilinear().scale(clip, format=clip.format.replace(subsampling_w=0, subsampling_h=0), range=ColorRange.FULL)
        pre = norm_expr(split(pre), "x y neutral - abs 0.25 * z neutral - abs 0.25 * + + 0 max mask_max min")
    else:
        pre = norm_expr(clip, "x 0 max mask_max min")

    mask = dynamic_ref(pre)
    letterbox = pre.letterbox.Find(ref=mask, ref_thr=dynamic_ref_thr)
    letterbox = letterbox.akarin.PropExpr(lambda: dict(
        VSLETTERBOX_TOP_ROW=f"x.VSLETTERBOX_TOP_ROW {permanent_top_row} 1 + <= {permanent_top_row} x.VSLETTERBOX_TOP_ROW ?",
        VSLETTERBOX_BOTTOM_ROW=f"x.VSLETTERBOX_BOTTOM_ROW {permanent_bottom_row} 1 - >= {permanent_bottom_row} x.VSLETTERBOX_BOTTOM_ROW ?"
    ))
    return letterbox

def letterbox_mask(
        clip,
        permanent=[0, 0],
        dynamic_ref=ExKirsch().edgemask,
        dynamic_ref_thr=2/3,
        fullblack_thr=1/5
    ):
    assert permanent[0] >= 0
    assert permanent[1] >= 0
    assert permanent[0] + permanent[1] < clip.height - 4
    permanent_top_row = permanent[0]
    permanent_bottom_row = clip.height - 1 - permanent[1]
    assert dynamic_ref_thr >= 0.0 and dynamic_ref_thr <= 1.0
    assert fullblack_thr >= 0.0 and fullblack_thr <= 1.0

    letterbox = find_letterbox(clip, permanent, dynamic_ref, dynamic_ref_thr)
    letterbox = letterbox.akarin.PropExpr(lambda: dict(_VSLETTERBOX_AREA_MULTIPLIER=f"""
x.VSLETTERBOX_BOTTOM_ROW 1 + x.VSLETTERBOX_TOP_ROW - {permanent_bottom_row} 1 + {permanent_top_row} - /
{fullblack_thr} /
"""))
    letterbox_mask = norm_expr(letterbox, f"""
Y {permanent_top_row} < mask_max
    Y x.VSLETTERBOX_TOP_ROW < mask_max x._VSLETTERBOX_AREA_MULTIPLIER *
        Y {permanent_bottom_row} > mask_max
            Y x.VSLETTERBOX_BOTTOM_ROW > mask_max x._VSLETTERBOX_AREA_MULTIPLIER *
            0 ? ? ? ?
""")
    return letterbox_mask

def clean_letterbox(
        clip,
        thr=0.030,
        transition=0.020,
        permanent=[0, 0],
        dynamic=True,
        dynamic_ref=ExKirsch().edgemask,
        dynamic_ref_thr=2/3,
        fullblack_thr=1/5,
        border_y=None,
        border_u=None,
        border_v=None
    ):
    assert permanent[0] >= 0
    assert permanent[1] >= 0
    assert permanent[0] + permanent[1] < clip.height - 4
    permanent_top_row = permanent[0]
    permanent_bottom_row = clip.height - 1 - permanent[1]
    assert dynamic_ref_thr >= 0.0 and dynamic_ref_thr <= 1.0
    assert fullblack_thr >= 0.0 and fullblack_thr <= 1.0

    if dynamic:
        letterbox = find_letterbox(clip, permanent, dynamic_ref, dynamic_ref_thr)
    else:
        letterbox = get_y(clip)
        letterbox = letterbox.std.SetFrameProps(VSLETTERBOX_TOP_ROW=permanent_top_row, VSLETTERBOX_BOTTOM_ROW=permanent_bottom_row)
    letterbox = letterbox.akarin.PropExpr(lambda: dict(_VSLETTERBOX_AREA_MULTIPLIER=f"""
x.VSLETTERBOX_BOTTOM_ROW 1 + x.VSLETTERBOX_TOP_ROW - {permanent_bottom_row} 1 + {permanent_top_row} - /
{fullblack_thr} /
"""))
    letterbox_mask = norm_expr(letterbox, f"""
plane_max plane_min - range!
{thr} range@ * plane_min + thr!
{transition} range@ * transition!
Y {permanent_top_row} < mask_max thr@ x - transition@ / 0 1 clamp *
    Y x.VSLETTERBOX_TOP_ROW < mask_max x._VSLETTERBOX_AREA_MULTIPLIER * thr@ x - transition@ / 0 1 clamp *
        Y {permanent_bottom_row} > mask_max thr@ x - transition@ / 0 1 clamp *
            Y x.VSLETTERBOX_BOTTOM_ROW > mask_max x._VSLETTERBOX_AREA_MULTIPLIER * thr@ x - transition@ / 0 1 clamp *
            0 ? ? ? ?
""")
    letterbox_mask = Morpho.minimum(letterbox_mask)

    assert clip.format.num_planes in [1, 3]
    if clip.format.num_planes == 3:
        if clip.format.subsampling_h or clip.format.subsampling_w:
            letterbox_mask_uv = Morpho.minimum(letterbox_mask)
            letterbox_mask = join(letterbox_mask, letterbox_mask_uv, letterbox_mask_uv)
            letterbox_mask = Bilinear().scale(letterbox_mask, format=clip.format, chromaloc=ChromaLocation.from_video(clip))
        else:
            letterbox_mask = join(letterbox_mask, letterbox_mask, letterbox_mask)
    clean = norm_expr([clip, letterbox_mask], ("""
y mask_max / mask!
x plane_min - 1 mask@ - * plane_min +
""", """
y mask_max / mask!
x 1 mask@ - * neutral mask@ * +
"""))
    clean = core.akarin.PropExpr([clean, letterbox_mask], lambda: dict(
        VSLETTERBOX_TOP_ROW="y.VSLETTERBOX_TOP_ROW",
        VSLETTERBOX_BOTTOM_ROW="y.VSLETTERBOX_BOTTOM_ROW",
        _VSLETTERBOX_AREA_MULTIPLIER="y._VSLETTERBOX_AREA_MULTIPLIER"
    ))

    if border_y or border_u or border_v:
        def border(clip, top_row, bottom_row, f):
            combine = []
            if top_row != 0:
                process = clip.std.CropAbs(top=0, height=top_row, width=clip.width)
                combine.append(process)
            process = clip.std.CropAbs(top=top_row, height=bottom_row+1-top_row, width=clip.width)
            process = f(process)
            combine.append(process)
            if bottom_row != clip.height - 1:
                process = clip.std.CropAbs(top=bottom_row+1, height=clip.height-bottom_row-1, width=clip.width)
                combine.append(process)
            return core.std.StackVertical(combine)

        clean_planes = split(clean)
        for plane in range(clean.format.num_planes):
            plane_name = ["y", "u", "v"][plane]
            border_p = locals()[f"border_{plane_name}"]
            if border_p:
                clean_p = clean_planes[plane]
                if not plane or not clip.format.subsampling_h:
                    standard_border_p = border(clean_p, permanent_top_row, permanent_bottom_row, border_p)
                    def border_eval(n, f, clean_p, standard_border_p, border, border_p):
                        if f.props["VSLETTERBOX_TOP_ROW"] == permanent_top_row and \
                           f.props["VSLETTERBOX_BOTTOM_ROW"] == permanent_bottom_row:
                            return standard_border_p
                        else:
                            return border(clean_p, f.props["VSLETTERBOX_TOP_ROW"], f.props["VSLETTERBOX_BOTTOM_ROW"], border_p)
                    process_p = core.std.FrameEval(clean_p, partial(border_eval, clean_p=clean_p, standard_border_p=standard_border_p, border=border, border_p=border_p), prop_src=clean_p)
                else:
                    assert clip.format.subsampling_h == 1
                    standard_border_p = border(clean_p, permanent_top_row >> 1, (permanent_bottom_row + 1) >> 1, border_p)
                    def border_eval(n, f, clean_p, standard_border_p, border, border_p):
                        if f.props["VSLETTERBOX_TOP_ROW"] == permanent_top_row >> 1 and \
                           f.props["VSLETTERBOX_BOTTOM_ROW"] == (permanent_bottom_row + 1) >> 1:
                            return standard_border_p
                        else:
                            return border(clean_p, f.props["VSLETTERBOX_TOP_ROW"] >> 1, (f.props["VSLETTERBOX_BOTTOM_ROW"] + 1) >> 1, border_p)
                    process_p = core.std.FrameEval(clean_p, partial(border_eval, clean_p=clean_p, standard_border_p=standard_border_p, border=border, border_p=border_p), prop_src=clean_p)
                clean_planes[plane] = process_p
        clean = join(clean_planes)

    return clean
