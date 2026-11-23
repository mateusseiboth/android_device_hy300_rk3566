/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#define LOG_TAG "hy300-sensors"

#include "AccelSensor.h"

#include <android-base/logging.h>
#include <time.h>

#include <algorithm>
#include <chrono>

namespace hy300::sensors {
namespace {

using aidl::android::hardware::sensors::BnSensors;
using aidl::android::hardware::sensors::SensorStatus;
using aidl::android::hardware::sensors::SensorType;
using EventPayload = aidl::android::hardware::sensors::Event::EventPayload;
using MetaDataEventType = EventPayload::MetaData::MetaDataEventType;

constexpr float kGravity = 9.80665f;
constexpr int32_t kMinDelayUs = 10 * 1000;     // 100 Hz
constexpr int32_t kMaxDelayUs = 1000 * 1000;   // 1 Hz
constexpr int64_t kDefaultPeriodNs = 200'000'000;

int64_t nowBoottimeNs() {
    timespec now{};
    clock_gettime(CLOCK_BOOTTIME, &now);
    return now.tv_sec * 1'000'000'000LL + now.tv_nsec;
}

AccelSensor::SensorInfo buildInfo(int32_t handle) {
    AccelSensor::SensorInfo info;
    info.sensorHandle = handle;
    info.name = "HY300 Accelerometer";
    info.vendor = "HY300";
    info.version = 1;
    info.type = SensorType::ACCELEROMETER;
    info.typeAsString = "android.sensor.accelerometer";
    // SC7A20 em +-2 g, 12 bits.
    info.maxRange = 2.f * kGravity;
    info.resolution = kGravity / 1024.f;
    info.power = 0.01f;  // mA
    info.minDelayUs = kMinDelayUs;
    info.maxDelayUs = kMaxDelayUs;
    info.fifoReservedEventCount = 0;
    info.fifoMaxEventCount = 0;
    info.requiredPermission = "";
    info.flags = 0;  // contínuo, sem acordar
    return info;
}

}  // namespace

AccelSensor::AccelSensor(int32_t handle, std::unique_ptr<AccelReader> reader,
                         std::unique_ptr<AccelControl> control, EventSink sink)
    : info_(buildInfo(handle)),
      reader_(std::move(reader)),
      control_(std::move(control)),
      sink_(std::move(sink)),
      periodNs_(kDefaultPeriodNs),
      thread_([this] { run(); }) {}

AccelSensor::~AccelSensor() {
    {
        std::lock_guard lock(mutex_);
        stop_ = true;
    }
    wake_.notify_all();
    thread_.join();
}

void AccelSensor::activate(bool enable) {
    std::lock_guard lock(mutex_);
    if (enabled_ == enable) {
        return;
    }
    enabled_ = enable;
    if (control_ && enable) {
        LOG_IF(WARNING, !control_->start(static_cast<int>(periodNs_ / 1'000'000)))
                << "não deu para ligar a medição do acelerômetro no kernel";
    }
    if (control_ && !enable) {
        control_->stop();
    }
    wake_.notify_all();
}

void AccelSensor::batch(int64_t samplingPeriodNs) {
    std::lock_guard lock(mutex_);
    periodNs_ = std::clamp<int64_t>(samplingPeriodNs, kMinDelayUs * 1000LL, kMaxDelayUs * 1000LL);
    if (control_ && enabled_) {
        control_->start(static_cast<int>(periodNs_ / 1'000'000));
    }
    wake_.notify_all();
}

ndk::ScopedAStatus AccelSensor::flush() {
    {
        std::lock_guard lock(mutex_);
        if (!enabled_) {
            return ndk::ScopedAStatus::fromServiceSpecificError(BnSensors::ERROR_BAD_VALUE);
        }
    }
    Event event;
    event.sensorHandle = info_.sensorHandle;
    event.sensorType = SensorType::META_DATA;
    EventPayload::MetaData meta;
    meta.what = MetaDataEventType::META_DATA_FLUSH_COMPLETE;
    event.payload.set<EventPayload::Tag::meta>(meta);
    sink_({event});
    return ndk::ScopedAStatus::ok();
}

void AccelSensor::setOperationMode(OperationMode mode) {
    std::lock_guard lock(mutex_);
    mode_ = mode;
    wake_.notify_all();
}

void AccelSensor::postSample() {
    const auto sample = reader_->read();
    if (!sample) {
        return;
    }
    Event event;
    event.timestamp = nowBoottimeNs();
    event.sensorHandle = info_.sensorHandle;
    event.sensorType = SensorType::ACCELEROMETER;
    EventPayload::Vec3 vec3;
    vec3.x = sample->x;
    vec3.y = sample->y;
    vec3.z = sample->z;
    vec3.status = SensorStatus::ACCURACY_HIGH;
    event.payload.set<EventPayload::Tag::vec3>(vec3);
    sink_({event});
}

void AccelSensor::run() {
    std::unique_lock lock(mutex_);
    while (!stop_) {
        if (!enabled_ || mode_ != OperationMode::NORMAL) {
            wake_.wait(lock, [this] { return stop_ || (enabled_ && mode_ == OperationMode::NORMAL); });
            continue;
        }
        lock.unlock();
        postSample();
        lock.lock();
        wake_.wait_for(lock, std::chrono::nanoseconds(periodNs_));
    }
}

}  // namespace hy300::sensors
