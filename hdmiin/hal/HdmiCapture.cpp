/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#define LOG_TAG "hy300-hdmiin"

#include "HdmiCapture.h"

#include <android-base/logging.h>
#include <android/native_window_aidl.h>

#include <chrono>

#include "CaptureStream.h"
#include "PreviewPump.h"
#include "RgaBlitter.h"
#include "V4l2FdDevice.h"
#include "WindowSink.h"

namespace hy300::hdmiin {
namespace {

constexpr uint32_t kCaptureBuffers = 4;
constexpr int kFrameTimeoutMs = 100;
constexpr auto kNoSignalWait = std::chrono::milliseconds(250);
constexpr auto kSignalCheck = std::chrono::seconds(1);

std::optional<CaptureSize> toCaptureSize(const hy300::tvinput::SignalState& state) {
    if (!state.timing) {
        return std::nullopt;
    }
    return CaptureSize{static_cast<uint32_t>(state.timing->width),
                       static_cast<uint32_t>(state.timing->height)};
}

// Captura até o sinal mudar (ou o pedido de parada): devolve para o laço de fora reconfigurar.
void runCapture(const std::string& videoPath, hy300::tvinput::V4l2Probe& probe, CaptureSize size,
                WindowSink& sink, const std::atomic_bool& stop) {
    V4l2FdDevice device(videoPath);
    CaptureStream stream(device);
    RgaBlitter blitter;
    if (!device.isOpen() || !stream.configure(size.width, size.height, kCaptureBuffers) ||
        !sink.setGeometry(stream.format().width, stream.format().height) || !stream.start()) {
        LOG(ERROR) << "captura não começou em " << size.width << "x" << size.height;
        std::this_thread::sleep_for(kNoSignalWait);
        return;
    }
    LOG(INFO) << "captura " << size.width << "x" << size.height;
    PreviewPump pump(stream, sink, blitter);
    auto nextCheck = std::chrono::steady_clock::now() + kSignalCheck;
    while (!stop) {
        pump.runOnce(kFrameTimeoutMs);
        if (std::chrono::steady_clock::now() < nextCheck) {
            continue;
        }
        nextCheck = std::chrono::steady_clock::now() + kSignalCheck;
        if (needsRestart(size, toCaptureSize(probe.read()))) {
            LOG(INFO) << "sinal mudou: recomeça a captura";
            return;
        }
    }
}

}  // namespace

HdmiCapture::HdmiCapture(std::string videoPath, std::string subdevPath)
    : videoPath_(std::move(videoPath)), subdevPath_(std::move(subdevPath)) {}

HdmiCapture::~HdmiCapture() {
    std::lock_guard lock(mutex_);
    stopLocked();
}

ndk::ScopedAStatus HdmiCapture::getSignal(HdmiSignal* result) {
    hy300::tvinput::V4l2Probe probe(subdevPath_);
    const auto state = probe.read();
    result->cablePresent = state.cablePresent;
    result->width = state.timing ? state.timing->width : 0;
    result->height = state.timing ? state.timing->height : 0;
    return ndk::ScopedAStatus::ok();
}

ndk::ScopedAStatus HdmiCapture::startPreview(const aidl::android::view::Surface& surface) {
    ANativeWindow* window = surface.get();
    if (window == nullptr) {
        return ndk::ScopedAStatus::fromExceptionCode(EX_ILLEGAL_ARGUMENT);
    }
    std::lock_guard lock(mutex_);
    stopLocked();
    ANativeWindow_acquire(window);
    stop_ = false;
    thread_ = std::thread([this, window] {
        run(window);
        ANativeWindow_release(window);
    });
    return ndk::ScopedAStatus::ok();
}

ndk::ScopedAStatus HdmiCapture::stopPreview() {
    std::lock_guard lock(mutex_);
    stopLocked();
    return ndk::ScopedAStatus::ok();
}

void HdmiCapture::stopLocked() {
    stop_ = true;
    if (thread_.joinable()) {
        thread_.join();
    }
}

void HdmiCapture::run(ANativeWindow* window) {
    WindowSink sink(window);
    hy300::tvinput::V4l2Probe probe(subdevPath_);
    while (!stop_) {
        const auto size = toCaptureSize(probe.read());
        if (!size) {
            std::this_thread::sleep_for(kNoSignalWait);
            continue;
        }
        runCapture(videoPath_, probe, *size, sink, stop_);
    }
}

}  // namespace hy300::hdmiin
