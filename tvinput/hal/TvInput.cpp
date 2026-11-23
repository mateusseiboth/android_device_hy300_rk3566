/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#define LOG_TAG "hy300-tvinput"

#include "TvInput.h"

#include <aidl/android/media/audio/common/AudioDeviceDescription.h>
#include <aidlcommonsupport/NativeHandle.h>
#include <android-base/logging.h>
#include <cutils/native_handle.h>
#include <fcntl.h>
#include <linux/videodev2.h>

#include <chrono>

namespace hy300::tvinput {

using aidl::android::hardware::tv::input::CableConnectionStatus;
using aidl::android::hardware::tv::input::TvInputDeviceInfo;
using aidl::android::hardware::tv::input::TvInputEvent;
using aidl::android::hardware::tv::input::TvInputEventType;
using aidl::android::hardware::tv::input::TvInputType;
using aidl::android::media::audio::common::AudioDevice;
using aidl::android::media::audio::common::AudioDeviceAddress;
using aidl::android::media::audio::common::AudioDeviceDescription;
using aidl::android::media::audio::common::AudioDeviceType;
using ndk::ScopedAStatus;

namespace {

ScopedAStatus fail(int32_t status) {
    return ScopedAStatus::fromServiceSpecificError(status);
}

CableConnectionStatus toAidl(Cable cable) {
    switch (cable) {
        case Cable::kConnected:
            return CableConnectionStatus::CONNECTED;
        case Cable::kDisconnected:
            return CableConnectionStatus::DISCONNECTED;
        case Cable::kUnknown:
            break;
    }
    return CableConnectionStatus::UNKNOWN;
}

// "HDMI In" do audio_policy, no endereço ALSA da placa rockchiphdmiin: o framework faz o
// patch de software dele para a saída atual quando a entrada é aberta.
AudioDevice buildAudioDevice(const std::string& address) {
    AudioDevice device;
    device.type.type = AudioDeviceType::IN_DEVICE;
    device.type.connection = AudioDeviceDescription::CONNECTION_HDMI;
    device.address = AudioDeviceAddress::make<AudioDeviceAddress::Tag::id>(address);
    return device;
}

}  // namespace

TvInput::TvInput(HdmiInConfig config, std::string videoPath, std::string subdevPath)
    : config_(std::move(config)),
      videoPath_(std::move(videoPath)),
      probe_(std::move(subdevPath)),
      thread_([this] { run(); }) {}

TvInput::~TvInput() {
    stop_ = true;
    thread_.join();
}

void TvInput::notifyLocked(TvInputEventType type) {
    if (!callback_) {
        return;
    }
    TvInputEvent event;
    event.type = type;
    event.deviceInfo.deviceId = kDeviceId;
    event.deviceInfo.type = TvInputType::HDMI;
    event.deviceInfo.portId = kPortId;
    event.deviceInfo.cableConnectionStatus = toAidl(toCable(tracker_.current()));
    event.deviceInfo.audioDevice = buildAudioDevice(config_.audioAddress);
    callback_->notify(event);
}

void TvInput::run() {
    while (!stop_) {
        const SignalState state = probe_.read();
        {
            std::lock_guard lock(mutex_);
            if (tracker_.update(state)) {
                LOG(INFO) << "HDMI: cabo " << state.cablePresent << ", "
                          << (state.timing ? std::to_string(state.timing->width) + "x" +
                                                     std::to_string(state.timing->height)
                                           : std::string("sem sinal"));
                notifyLocked(TvInputEventType::STREAM_CONFIGURATIONS_CHANGED);
            }
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(config_.pollMs));
    }
}

ScopedAStatus TvInput::setCallback(const std::shared_ptr<ITvInputCallback>& callback) {
    std::lock_guard lock(mutex_);
    callback_ = callback;
    notifyLocked(TvInputEventType::DEVICE_AVAILABLE);
    return ScopedAStatus::ok();
}

ScopedAStatus TvInput::getStreamConfigurations(int32_t deviceId,
                                               std::vector<TvStreamConfig>* result) {
    if (deviceId != kDeviceId) {
        return fail(STATUS_INVALID_ARGUMENTS);
    }
    std::lock_guard lock(mutex_);
    result->clear();
    for (const auto& config : buildStreamConfigs(tracker_.current())) {
        TvStreamConfig aidl;
        aidl.streamId = config.streamId;
        aidl.maxVideoWidth = config.width;
        aidl.maxVideoHeight = config.height;
        result->push_back(aidl);
    }
    return ScopedAStatus::ok();
}

ScopedAStatus TvInput::openStream(int32_t deviceId, int32_t streamId, NativeHandle* result) {
    if (deviceId != kDeviceId || streamId != kStreamId) {
        return fail(STATUS_INVALID_ARGUMENTS);
    }
    std::lock_guard lock(mutex_);
    const auto timing = tracker_.current().timing;
    if (!timing) {
        return fail(STATUS_INVALID_STATE);
    }
    if (stream_.get() >= 0) {
        return fail(STATUS_NO_RESOURCE);
    }
    stream_.reset(open(videoPath_.c_str(), O_RDWR | O_CLOEXEC));
    if (stream_.get() < 0) {
        PLOG(ERROR) << "não abriu " << videoPath_;
        return fail(STATUS_UNKNOWN);
    }
    const auto ints = buildSidebandInts(*timing, V4L2_PIX_FMT_NV12);
    native_handle_t* handle = native_handle_create(1, static_cast<int>(ints.size()));
    handle->data[0] = stream_.get();
    std::copy(ints.begin(), ints.end(), handle->data + 1);
    *result = android::dupToAidl(handle);
    native_handle_delete(handle);
    return ScopedAStatus::ok();
}

ScopedAStatus TvInput::closeStream(int32_t deviceId, int32_t streamId) {
    if (deviceId != kDeviceId || streamId != kStreamId) {
        return fail(STATUS_INVALID_ARGUMENTS);
    }
    std::lock_guard lock(mutex_);
    if (stream_.get() < 0) {
        return fail(STATUS_INVALID_STATE);
    }
    stream_.reset();
    return ScopedAStatus::ok();
}

ScopedAStatus TvInput::setTvMessageEnabled(int32_t, int32_t, TvMessageEventType, bool) {
    return ScopedAStatus::ok();
}

ScopedAStatus TvInput::getTvMessageQueueDesc(ByteQueueDescriptor*, int32_t, int32_t) {
    return ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
}

}  // namespace hy300::tvinput
