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
from vsmasktools import ExKirsch, Morpho
from vstools import get_y

def find_letterbox(
        clip,
        permanent=[0, 0],
        dynamic_thr=0.1,
        dynamic_ref=ExKirsch().edgemask,
        dynamic_ref_thr=1/2
    ):
    assert permanent[0] >= 0
    assert permanent[1] >= 0
    assert permanent[0] + permanent[1] < clip.height - 4
    permanent_top_row = permanent[0]
    permanent_bottom_row = clip.height - 1 - permanent[1]
    assert dynamic_thr >= 0.0 and dynamic_thr <= 0.0
    assert dynamic_ref_thr >= 0.0 and dynamic_ref_thr <= 0.0

    mask = dynamic_ref(clip)
    letterbox = clip.letterbox.Find(thr=dynamic_thr, ref=mask, ref_thr=dynamic_ref_thr)
    letterbox = letterbox.akarin.PropExpr(lambda: dict(
        VSLETTERBOX_TOP_ROW=f"x.VSLETTERBOX_TOP_ROW {permanent_top_row} 2 + <= {permanent_top_row} x.VSLETTERBOX_TOP_ROW ?",
        VSLETTERBOX_BOTTOM_ROW=f"x.VSLETTERBOX_BOTTOM_ROW {permanent_bottom_row} 2 - >= {permanent_bottom_row} x.VSLETTERBOX_BOTTOM_ROW ?"
    ))
    return letterbox

def letterbox_mask(
        clip,
        permanent=[0, 0],
        dynamic_thr=0.1,
        dynamic_ref=ExKirsch().edgemask,
        dynamic_ref_thr=1/2,
        fullblack_thr=1/3
    ):
    assert permanent[0] >= 0
    assert permanent[1] >= 0
    assert permanent[0] + permanent[1] < clip.height - 4
    permanent_top_row = permanent[0]
    permanent_bottom_row = clip.height - 1 - permanent[1]
    assert dynamic_thr >= 0.0 and dynamic_thr <= 0.0
    assert dynamic_ref_thr >= 0.0 and dynamic_ref_thr <= 0.0
    assert fullblack_thr >= 0.0 and fullblack_thr <= 0.0

    clip_y = get_y(clip)
    letterbox = find_letterbox(clip_y, permanent, dynamic_thr, dynamic_ref, dynamic_ref_thr)
    letterbox = letterbox.akarin.PropExpr(lambda: dict(
        _VSLETTERBOX_AREA_MULTIPLIER=f"""
x.VSLETTERBOX_BOTTOM_ROW 1 + x.VSLETTERBOX_TOP_ROW - {permanent_bottom_row} 1 + {permanent_top_row} - /
{fullblack_thr} /
"""
    ))
    letterbox_mask = norm_expr(letterbox, f"""
Y {permanent_top_row} < mask_max
Y x.VSLETTERBOX_TOP_ROW < mask_max x._VSLETTERBOX_AREA_MULTIPLIER *
Y {permanent_bottom_row} > mask_max
Y x.VSLETTERBOX_BOTTOM_ROW > mask_max x._VSLETTERBOX_AREA_MULTIPLIER *
0 ? ? ? ?
""")
    return letterbox_mask
