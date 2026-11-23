/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#define LOG_TAG "hy300-hdmiin"

#include "WindowSink.h"

#include <android-base/logging.h>
#include <android/hardware_buffer.h>
#include <android/sync.h>
#include <unistd.h>
#include <vndk/window.h>

namespace hy300::hdmiin {
namespace {

// Fila curta: dois buffers na Surface além do que o compositor segura.
constexpr int kWindowBuffers = 3;

}  // namespace

WindowSink::WindowSink(ANativeWindow* window) : window_(window) {
    ANativeWindow_acquire(window_);
}

WindowSink::~WindowSink() {
    ANativeWindow_release(window_);
}

bool WindowSink::setGeometry(uint32_t width, uint32_t height) {
    ANativeWindow_setUsage(window_, AHARDWAREBUFFER_USAGE_GPU_SAMPLED_IMAGE |
                                            AHARDWAREBUFFER_USAGE_COMPOSER_OVERLAY);
    ANativeWindow_setBufferCount(window_, kWindowBuffers);
    return ANativeWindow_setBuffersGeometry(window_, static_cast<int32_t>(width),
                                            static_cast<int32_t>(height),
                                            AHARDWAREBUFFER_FORMAT_R8G8B8A8_UNORM) == 0;
}

std::optional<GraphicTarget> WindowSink::dequeue() {
    ANativeWindowBuffer* buffer = nullptr;
    int fence = -1;
    if (ANativeWindow_dequeueBuffer(window_, &buffer, &fence) != 0 || buffer == nullptr) {
        return std::nullopt;
    }
    if (fence >= 0) {
        sync_wait(fence, -1);
        close(fence);
    }
    if (buffer->handle == nullptr || buffer->handle->numFds < 1) {
        ANativeWindow_cancelBuffer(window_, buffer, -1);
        return std::nullopt;
    }
    return GraphicTarget{buffer->handle->data[0], static_cast<uint32_t>(buffer->width),
                         static_cast<uint32_t>(buffer->height), static_cast<uint32_t>(buffer->stride),
                         buffer};
}

void WindowSink::queue(const GraphicTarget& target) {
    ANativeWindow_queueBuffer(window_, static_cast<ANativeWindowBuffer*>(target.token), -1);
}

void WindowSink::cancel(const GraphicTarget& target) {
    ANativeWindow_cancelBuffer(window_, static_cast<ANativeWindowBuffer*>(target.token), -1);
}

}  // namespace hy300::hdmiin
