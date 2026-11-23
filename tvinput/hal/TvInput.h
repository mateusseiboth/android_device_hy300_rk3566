/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <aidl/android/hardware/tv/input/BnTvInput.h>
#include <android-base/thread_annotations.h>
#include <android-base/unique_fd.h>

#include <atomic>
#include <map>
#include <memory>
#include <mutex>
#include <thread>

#include "HdmiInCore.h"
#include "V4l2Probe.h"

namespace hy300::tvinput {

// HAL de TV input (AIDL V1) com uma entrada HDMI, a do RK628. Acompanha o cabo e a resolução
// numa thread e avisa o framework (TvInputHardwareManager), que liga o áudio do "HDMI In" ao
// alto-falante pelo audio_policy. O stream é um sideband com o fd do /dev/videoN de captura;
// o compositor que o consome ainda não existe (ver docs).
class TvInput : public aidl::android::hardware::tv::input::BnTvInput {
  public:
    using ITvInputCallback = aidl::android::hardware::tv::input::ITvInputCallback;
    using TvStreamConfig = aidl::android::hardware::tv::input::TvStreamConfig;
    using TvMessageEventType = aidl::android::hardware::tv::input::TvMessageEventType;
    using NativeHandle = aidl::android::hardware::common::NativeHandle;
    using ByteQueueDescriptor = aidl::android::hardware::common::fmq::MQDescriptor<
            int8_t, aidl::android::hardware::common::fmq::SynchronizedReadWrite>;

    TvInput(HdmiInConfig config, std::string videoPath, std::string subdevPath);
    ~TvInput() override;

    ndk::ScopedAStatus setCallback(const std::shared_ptr<ITvInputCallback>& callback) override;
    ndk::ScopedAStatus getStreamConfigurations(int32_t deviceId,
                                               std::vector<TvStreamConfig>* result) override;
    ndk::ScopedAStatus openStream(int32_t deviceId, int32_t streamId,
                                  NativeHandle* result) override;
    ndk::ScopedAStatus closeStream(int32_t deviceId, int32_t streamId) override;
    ndk::ScopedAStatus setTvMessageEnabled(int32_t deviceId, int32_t streamId,
                                           TvMessageEventType type, bool enabled) override;
    ndk::ScopedAStatus getTvMessageQueueDesc(ByteQueueDescriptor* queue, int32_t deviceId,
                                             int32_t streamId) override;

  private:
    void run();
    void notifyLocked(aidl::android::hardware::tv::input::TvInputEventType type)
            REQUIRES(mutex_);

    const HdmiInConfig config_;
    const std::string videoPath_;
    V4l2Probe probe_;

    std::mutex mutex_;
    std::shared_ptr<ITvInputCallback> callback_ GUARDED_BY(mutex_);
    HdmiInTracker tracker_ GUARDED_BY(mutex_);
    android::base::unique_fd stream_ GUARDED_BY(mutex_);
    std::atomic_bool stop_ = false;
    std::thread thread_;
};

}  // namespace hy300::tvinput
