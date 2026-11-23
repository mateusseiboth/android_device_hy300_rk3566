/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <aidl/vendor/hy300/hdmiin/BnHdmiCapture.h>
#include <android/native_window.h>

#include <atomic>
#include <mutex>
#include <string>
#include <thread>

#include "V4l2Probe.h"

namespace hy300::hdmiin {

// Serviço vendor.hy300.hdmiin.IHdmiCapture/default: prévia da entrada HDMI numa Surface do app.
class HdmiCapture : public aidl::vendor::hy300::hdmiin::BnHdmiCapture {
  public:
    using HdmiSignal = aidl::vendor::hy300::hdmiin::HdmiSignal;

    HdmiCapture(std::string videoPath, std::string subdevPath);
    ~HdmiCapture() override;

    ndk::ScopedAStatus getSignal(HdmiSignal* result) override;
    ndk::ScopedAStatus startPreview(const aidl::android::view::Surface& surface) override;
    ndk::ScopedAStatus stopPreview() override;

  private:
    void run(ANativeWindow* window);
    void stopLocked();

    const std::string videoPath_;
    const std::string subdevPath_;
    std::mutex mutex_;
    std::atomic_bool stop_ = false;
    std::thread thread_;
};

}  // namespace hy300::hdmiin
