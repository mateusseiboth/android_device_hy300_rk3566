/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#include "CaptureStream.h"

#include <fcntl.h>
#include <linux/videodev2.h>
#include <unistd.h>

#include <cerrno>
#include <cstring>

namespace hy300::hdmiin {
namespace {

constexpr uint32_t kType = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;

}  // namespace

bool needsRestart(const CaptureSize& configured, const std::optional<CaptureSize>& signal) {
    return !signal || !(*signal == configured);
}

CaptureStream::CaptureStream(V4l2Device& device) : device_(device) {}

CaptureStream::~CaptureStream() {
    stop();
}

bool CaptureStream::configure(uint32_t width, uint32_t height, uint32_t bufferCount) {
    stop();
    v4l2_format format{};
    format.type = kType;
    format.fmt.pix_mp.width = width;
    format.fmt.pix_mp.height = height;
    format.fmt.pix_mp.pixelformat = V4L2_PIX_FMT_NV12;
    format.fmt.pix_mp.field = V4L2_FIELD_NONE;
    format.fmt.pix_mp.num_planes = 1;
    if (device_.xioctl(VIDIOC_S_FMT, &format) != 0 ||
        format.fmt.pix_mp.pixelformat != V4L2_PIX_FMT_NV12 || format.fmt.pix_mp.num_planes != 1) {
        return false;
    }
    format_ = {format.fmt.pix_mp.width, format.fmt.pix_mp.height, format.fmt.pix_mp.pixelformat,
               format.fmt.pix_mp.plane_fmt[0].bytesperline,
               format.fmt.pix_mp.plane_fmt[0].sizeimage};

    v4l2_requestbuffers request{};
    request.count = bufferCount;
    request.type = kType;
    request.memory = V4L2_MEMORY_MMAP;
    if (device_.xioctl(VIDIOC_REQBUFS, &request) != 0 || request.count == 0) {
        return false;
    }
    for (uint32_t index = 0; index < request.count; ++index) {
        v4l2_exportbuffer exported{};
        exported.type = kType;
        exported.index = index;
        exported.plane = 0;
        exported.flags = O_RDONLY | O_CLOEXEC;
        if (device_.xioctl(VIDIOC_EXPBUF, &exported) != 0) {
            closeBuffers();
            return false;
        }
        dmabufs_.push_back(exported.fd);
    }
    return true;
}

bool CaptureStream::queue(uint32_t index) {
    v4l2_plane plane{};
    v4l2_buffer buffer{};
    buffer.type = kType;
    buffer.memory = V4L2_MEMORY_MMAP;
    buffer.index = index;
    buffer.length = 1;
    buffer.m.planes = &plane;
    return device_.xioctl(VIDIOC_QBUF, &buffer) == 0;
}

std::optional<uint32_t> CaptureStream::dequeue() {
    v4l2_plane plane{};
    v4l2_buffer buffer{};
    buffer.type = kType;
    buffer.memory = V4L2_MEMORY_MMAP;
    buffer.length = 1;
    buffer.m.planes = &plane;
    if (device_.xioctl(VIDIOC_DQBUF, &buffer) != 0) {
        return std::nullopt;
    }
    return buffer.index;
}

bool CaptureStream::start() {
    for (uint32_t index = 0; index < dmabufs_.size(); ++index) {
        if (!queue(index)) {
            return false;
        }
    }
    int type = kType;
    streaming_ = device_.xioctl(VIDIOC_STREAMON, &type) == 0;
    return streaming_;
}

void CaptureStream::stop() {
    if (streaming_) {
        int type = kType;
        device_.xioctl(VIDIOC_STREAMOFF, &type);
        streaming_ = false;
    }
    if (!dmabufs_.empty()) {
        closeBuffers();
        v4l2_requestbuffers request{};
        request.count = 0;
        request.type = kType;
        request.memory = V4L2_MEMORY_MMAP;
        device_.xioctl(VIDIOC_REQBUFS, &request);
    }
}

void CaptureStream::closeBuffers() {
    for (int fd : dmabufs_) {
        close(fd);
    }
    dmabufs_.clear();
}

std::optional<uint32_t> CaptureStream::acquireLatest(int timeoutMs) {
    if (!streaming_ || !device_.waitReadable(timeoutMs)) {
        return std::nullopt;
    }
    std::optional<uint32_t> latest;
    while (const auto index = dequeue()) {
        if (latest) {
            queue(*latest);
        }
        latest = index;
    }
    return latest;
}

bool CaptureStream::release(uint32_t index) {
    return queue(index);
}

int CaptureStream::dmabuf(uint32_t index) const {
    return index < dmabufs_.size() ? dmabufs_[index] : -1;
}

}  // namespace hy300::hdmiin
