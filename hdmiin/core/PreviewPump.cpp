/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#include "PreviewPump.h"

namespace hy300::hdmiin {

PreviewPump::PreviewPump(CaptureStream& stream, FrameSink& sink, Blitter& blitter)
    : stream_(stream), sink_(sink), blitter_(blitter) {}

PreviewPump::Step PreviewPump::runOnce(int timeoutMs) {
    const auto frame = stream_.acquireLatest(timeoutMs);
    if (!frame) {
        return Step::kNoFrame;
    }
    const auto target = sink_.dequeue();
    if (!target) {
        stream_.release(*frame);
        return Step::kNoTarget;
    }
    const bool copied = blitter_.blit(stream_.dmabuf(*frame), stream_.format(), *target);
    stream_.release(*frame);
    if (!copied) {
        sink_.cancel(*target);
        return Step::kBlitFailed;
    }
    sink_.queue(*target);
    return Step::kFrame;
}

}  // namespace hy300::hdmiin
