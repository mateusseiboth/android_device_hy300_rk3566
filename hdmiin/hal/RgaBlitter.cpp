/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#define LOG_TAG "hy300-hdmiin"

#include "RgaBlitter.h"

#include <android-base/logging.h>

#include <cstring>

#include "im2d.h"

namespace hy300::hdmiin {
namespace {

rga_buffer_handle_t importBuffer(int fd, int wstride, int hstride, int format) {
    im_handle_param_t param;
    std::memset(&param, 0, sizeof(param));
    param.width = static_cast<uint32_t>(wstride);
    param.height = static_cast<uint32_t>(hstride);
    param.format = static_cast<uint32_t>(format);
    return importbuffer_fd(fd, &param);
}

}  // namespace

bool RgaBlitter::blit(int srcFd, const CaptureFormat& src, const GraphicTarget& dst) {
    const int srcW = static_cast<int>(src.width);
    const int srcH = static_cast<int>(src.height);
    const int srcStride = static_cast<int>(src.bytesPerLine);
    const int dstW = static_cast<int>(dst.width);
    const int dstH = static_cast<int>(dst.height);
    const int dstStride = static_cast<int>(dst.stride);

    rga_buffer_handle_t srcHandle = importBuffer(srcFd, srcStride, srcH, RK_FORMAT_YCbCr_420_SP);
    rga_buffer_handle_t dstHandle = importBuffer(dst.fd, dstStride, dstH, RK_FORMAT_RGBA_8888);
    if (srcHandle == 0 || dstHandle == 0) {
        LOG(ERROR) << "RGA não importou os buffers";
        if (srcHandle != 0) releasebuffer_handle(srcHandle);
        if (dstHandle != 0) releasebuffer_handle(dstHandle);
        return false;
    }
    rga_buffer_t srcBuffer = wrapbuffer_handle(srcHandle, srcW, srcH, RK_FORMAT_YCbCr_420_SP,
                                               srcStride, srcH);
    rga_buffer_t dstBuffer = wrapbuffer_handle(dstHandle, dstW, dstH, RK_FORMAT_RGBA_8888,
                                               dstStride, dstH);
    const IM_STATUS status = improcess(srcBuffer, dstBuffer, {}, {}, {}, {}, IM_SYNC);
    releasebuffer_handle(srcHandle);
    releasebuffer_handle(dstHandle);
    LOG_IF(ERROR, status <= 0) << "RGA falhou: " << imStrError(status);
    return status > 0;
}

}  // namespace hy300::hdmiin
