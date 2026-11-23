/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 *
 * /dev/videoN falso para os testes no host: imita o rkisp (captura multiplanar, NV12, buffers
 * MMAP exportados como dma-buf) com uma fila de quadros prontos controlada pelo teste.
 */

#pragma once

#include <linux/videodev2.h>
#include <unistd.h>

#include <cerrno>
#include <cstring>
#include <deque>
#include <set>
#include <vector>

#include "V4l2Device.h"

namespace hy300::hdmiin {

class FakeV4l2 : public V4l2Device {
  public:
    int xioctl(unsigned long request, void* arg) override {
        calls.push_back(request);
        switch (request) {
            case VIDIOC_S_FMT:
                return setFormat(static_cast<v4l2_format*>(arg));
            case VIDIOC_REQBUFS:
                return requestBuffers(static_cast<v4l2_requestbuffers*>(arg));
            case VIDIOC_EXPBUF:
                return exportBuffer(static_cast<v4l2_exportbuffer*>(arg));
            case VIDIOC_QBUF:
                return queueBuffer(static_cast<v4l2_buffer*>(arg));
            case VIDIOC_DQBUF:
                return dequeueBuffer(static_cast<v4l2_buffer*>(arg));
            case VIDIOC_STREAMON:
                streaming = true;
                return 0;
            case VIDIOC_STREAMOFF:
                streaming = false;
                queued.clear();
                ready.clear();
                return 0;
            default:
                errno = ENOTTY;
                return -1;
        }
    }

    bool waitReadable(int /* timeoutMs */) override { return !ready.empty(); }

    // O "hardware" termina um quadro no buffer mais antigo da fila de entrada.
    bool finishFrame() {
        if (queued.empty()) return false;
        ready.push_back(queued.front());
        queued.pop_front();
        return true;
    }

    ~FakeV4l2() override {
        for (int fd : exportedFds) close(fd);
    }

    uint32_t acceptedFourcc = V4L2_PIX_FMT_NV12;
    uint32_t bufferCount = 0;
    bool streaming = false;
    std::deque<uint32_t> queued;
    std::deque<uint32_t> ready;
    std::vector<unsigned long> calls;
    std::vector<int> exportedFds;
    v4l2_format lastFormat{};

  private:
    int setFormat(v4l2_format* format) {
        if (format->type != V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE) {
            errno = EINVAL;
            return -1;
        }
        auto& pix = format->fmt.pix_mp;
        pix.pixelformat = acceptedFourcc;
        pix.num_planes = 1;
        pix.plane_fmt[0].bytesperline = (pix.width + 15) & ~15U;
        pix.plane_fmt[0].sizeimage = pix.plane_fmt[0].bytesperline * pix.height * 3 / 2;
        lastFormat = *format;
        return 0;
    }

    int requestBuffers(v4l2_requestbuffers* request) {
        if (request->memory != V4L2_MEMORY_MMAP) {
            errno = EINVAL;
            return -1;
        }
        bufferCount = request->count;
        return 0;
    }

    int exportBuffer(v4l2_exportbuffer* exported) {
        if (exported->index >= bufferCount) {
            errno = EINVAL;
            return -1;
        }
        exported->fd = dup(STDERR_FILENO);
        exportedFds.push_back(exported->fd);
        return 0;
    }

    int queueBuffer(v4l2_buffer* buffer) {
        if (buffer->index >= bufferCount || buffer->length != 1 || buffer->m.planes == nullptr) {
            errno = EINVAL;
            return -1;
        }
        queued.push_back(buffer->index);
        return 0;
    }

    int dequeueBuffer(v4l2_buffer* buffer) {
        if (ready.empty()) {
            errno = EAGAIN;
            return -1;
        }
        buffer->index = ready.front();
        ready.pop_front();
        return 0;
    }
};

}  // namespace hy300::hdmiin
