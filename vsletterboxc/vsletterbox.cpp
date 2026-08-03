// vapoursynth-letterbox
// Copyright (c) Akatsumekusa and contributors

// ---------------------------------------------------------------------
// Permission is hereby granted, free of charge, to any person obtaining
// a copy of this software and associated documentation files (the
// "Software"), to deal in the Software without restriction, including
// without limitation the rights to use, copy, modify, merge, publish,
// distribute, sublicense, and/or sell copies of the Software, and to
// permit persons to whom the Software is furnished to do so, subject to
// the following conditions:
// 
// The above copyright notice and this permission notice shall be
// included in all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
// EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
// NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
// BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
// ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
// CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.
// ---------------------------------------------------------------------

#include <algorithm>
#include <limits>
#include <memory>
#include <cstdint>
#include <cstring>
#include <type_traits>
#include <VapourSynth4.h>
#include <VSHelper4.h>

struct FindData {
    VSNode *clip;
    VSNode *ref;
    double  ref_thr;
    double  low_thr;
    double  high_thr;
};

template <typename T>
static inline double letterbox_search_get_frame_ref_mean(const T * VS_RESTRICT refp, int width) {
    T max_value;
    T min_value;
    if constexpr (std::is_integral_v<T>) {
        max_value = std::numeric_limits<T>::max();
        min_value = std::numeric_limits<T>::min();
    }
    else {
        max_value = 1.0;
        min_value = 0.0;
    }

    std::conditional_t<std::is_same_v<T, uint8_t>,
                       uint32_t,
                       std::conditional_t<std::is_same_v<T, uint16_t>,
                                          uint64_t,
                                          double>>
        sum = 0;
    if constexpr (std::is_integral_v<T>) {
        for (int x = 0; x < width; x++)
            sum += refp[x];
    }
    else {
        for (int x = 0; x < width; x++)
            sum += std::clamp(refp[x], min_value, max_value);
    }

    return (double)sum / width / max_value;
}

template <typename T>
static const VSFrame * VS_CC letterbox_search_get_frame(int n, int activationReason, void *instanceData, void **frameData, VSFrameContext *frameCtx, VSCore *core, const VSAPI *vsapi) {
    auto *d = static_cast<FindData *>(instanceData);

    if (activationReason == arInitial) {
        vsapi->requestFrameFilter(n, d->clip, frameCtx);
        vsapi->requestFrameFilter(n, d->ref, frameCtx);
    }
    else if (activationReason == arAllFramesReady) {
        const auto clip = vsapi->getFrameFilter(n, d->clip, frameCtx);
        if (!clip) {
            vsapi->setFilterError("vsletterbox: Failed to get frame from VapourSynth", frameCtx);
            return nullptr;
        }
        const auto ref  = vsapi->getFrameFilter(n, d->ref, frameCtx);
        if (!ref) {
            vsapi->freeFrame(clip);
            vsapi->setFilterError("vsletterbox: Failed to get frame from VapourSynth", frameCtx);
            return nullptr;
        }

        const auto ref_thr   = d->ref_thr;
        T          low_thr;
        T          high_thr;
        if constexpr (std::is_integral_v<T>) {
            low_thr          = static_cast<T>(std::clamp(d->low_thr, std::numeric_limits<T>::min(), std::numeric_limits<T>::max) + 0.5);
            high_thr         = static_cast<T>(std::clamp(d->high_thr, std::numeric_limits<T>::min(), std::numeric_limits<T>::max) + 0.5);
        }
        else {
            low_thr          = d->low_thr;
            high_thr         = d->high_thr;
        }

        const auto fi     = vsapi->getVideoFrameFormat(clip);
        const int  height = vsapi->getFrameHeight(clip, 0);
        const int  width  = vsapi->getFrameWidth(clip, 0);
        if (height != vsapi->getFrameHeight(ref, 0) ||
            width != vsapi->getFrameWidth(ref, 0)) {
            vsapi->freeFrame(clip);
            vsapi->freeFrame(ref);
            vsapi->setFilterError("vsletterbox: Both inputs must have the same height and width", frameCtx);
            return nullptr;
        }

        auto dst   = vsapi->copyFrame(clip, core);
        auto props = vsapi->getFramePropertiesRW(dst);

        const T * VS_RESTRICT ori_srcp   = static_cast<const T *>(vsapi->getReadPtr(clip, 0));
        const auto            src_stride = vsapi->getStride(clip, 0) / sizeof(T);
        const T * VS_RESTRICT ori_refp   = static_cast<const T *>(vsapi->getReadPtr(ref, 0));
        const auto            ref_stride = vsapi->getStride(ref, 0) / sizeof(T);

        int start_y = 0;
        int end_y = height - 1;

        auto srcp = ori_srcp;
        auto refp = ori_refp;
        auto exceed = false;
        for (; start_y < height; start_y++) {
            for (int x = 0; x < width; x++) {
                if (srcp[x] < low_thr || srcp[x] > high_thr) {
                    exceed = true;
                    break;
                }
            }
            if (exceed)
                break;

            srcp += src_stride;
            refp += ref_stride;
        }

        if (!exceed)
            start_y = height >> 1 + 1;
            end_y = height >> 1;
        else [[likely]] {
            if (letterbox_search_get_frame_ref_mean<T>(refp, width) < ref_thr)
                start_y = 0;

            srcp = ori_srcp + end_y * src_stride;
            refp = ori_refp + end_y * ref_stride;
            exceed = false;
            for (; end_y >= 0; end_y--) {
                for (int x = 0; x < width; x++) {
                    if (srcp[x] < low_thr || srcp[x] > high_thr) {
                        exceed = true;
                        break;
                    }
                }
                if (exceed)
                    break;

                srcp -= src_stride;
                refp -= ref_stride;
            }
            if (!exceed) {
                vsapi->freeFrame(clip);
                vsapi->freeFrame(ref);
                vsapi->freeFrame(dst);
                vsapi->setFilterError("vsletterbox: Unexpected internal bug \"exceed\"", frameCtx);
                return nullptr;
            }
            else [[likely]] {
                if (letterbox_search_get_frame_ref_mean<T>(refp, width) < ref_thr)
                    end_y = height - 1;
            }
        }

        const auto start_y_prop = "_VSLETTERBOX_TOP_ROW";
        const auto end_y_prop = "_VSLETTERBOX_BOTTOM_ROW";
        vsapi->mapSetInt(props, start_y_prop, start_y, maReplace);
        vsapi->mapSetInt(props, end_y_prop, end_y, maReplace);
            
        vsapi->freeFrame(clip);
        vsapi->freeFrame(ref);
    
        return dst;
    }

    return nullptr;
}

static void VS_CC letterbox_search_free(void *instanceData, VSCore *core, const VSAPI *vsapi) {
    auto *d = static_cast<FindData *>(instanceData);
    vsapi->freeNode(d->clip);
    vsapi->freeNode(d->ref);
    delete d;
}

static void VS_CC letterbox_search_create(const VSMap *in, VSMap *out, void *userData, VSCore *core, const VSAPI *vsapi) {
    std::unique_ptr<FindData> d(new FindData);

    d->clip           = vsapi->mapGetNode(in, "clip", 0, nullptr);
    const auto vi     = vsapi->getVideoInfo(d->clip);
    d->ref            = vsapi->mapGetNode(in, "ref", 0, nullptr);
    const auto ref_vi = vsapi->getVideoInfo(d->ref);
    if (!vsh::isConstantVideoFormat(vi) || !vsh::isConstantVideoFormat(ref_vi) ||
        vi->format.sampleType != ref_vi->format.sampleType ||
        vi->format.bitsPerSample != ref_vi->format.bitsPerSample ||
        vi->height != ref_vi->height ||
        vi->width != ref_vi->width) {
        vsapi->mapSetError(out, "vsletterbox: Both input must be of constant format, and of the same sample type, bits per sample, height, and width");
        vsapi->freeNode(d->clip);
        vsapi->freeNode(d->ref);
        return;
    }

    d->ref_thr  = vsapi->mapGetFloat(in, "ref_thr", 0, nullptr);
    d->low_thr  = vsapi->mapGetFloat(in, "low_thr", 0, nullptr);
    d->high_thr = vsapi->mapGetFloat(in, "high_thr", 0, nullptr);
    
    VSFilterDependency deps[] = {{d->clip, rpStrictSpatial}, {d->ref, rpStrictSpatial}};
    int num_deps = 2;

    if (vi->format.sampleType == stInteger && vi->format.bitsPerSample == 32)
        vsapi->createVideoFilter(out, "Find", vi, letterbox_search_get_frame<uint32_t>, letterbox_search_free, fmParallel, deps, num_deps, d.release(), core);
    else if (vi->format.sampleType == stInteger && vi->format.bitsPerSample == 16)
        vsapi->createVideoFilter(out, "Find", vi, letterbox_search_get_frame<uint16_t>, letterbox_search_free, fmParallel, deps, num_deps, d.release(), core);
    else if (vi->format.sampleType == stInteger && vi->format.bitsPerSample == 8)
        vsapi->createVideoFilter(out, "Find", vi, letterbox_search_get_frame<uint8_t>, letterbox_search_free, fmParallel, deps, num_deps, d.release(), core);
    else if (vi->format.sampleType == stFloat && vi->format.bitsPerSample == 32)
        vsapi->createVideoFilter(out, "Find", vi, letterbox_search_get_frame<float>, letterbox_search_free, fmParallel, deps, num_deps, d.release(), core);
    else {
        vsapi->mapSetError(out, "vsletterbox: Only 32-bit, 16-bit, or 8-bit integer format or 32-bit float format are supported");
        vsapi->freeNode(d->clip);
        vsapi->freeNode(d->ref);
        return;
    }
}

VS_EXTERNAL_API(void) VapourSynthPluginInit2(VSPlugin *plugin, const VSPLUGINAPI *vspapi) {
    vspapi->configPlugin("aka.letterbox", "letterbox", "Letterbox Detection and Masking", VS_MAKE_VERSION(1, 0), VAPOURSYNTH_API_VERSION, 0, plugin);
    vspapi->registerFunction("Find", "clip:vnode;"
                                     "ref:vnode;"
                                     "ref_thr:float;"
                                     "low_thr:float;"
                                     "high_thr:float;", "clip:vnode;", letterbox_search_create, NULL, plugin);
}
