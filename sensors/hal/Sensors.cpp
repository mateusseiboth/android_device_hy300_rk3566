/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#define LOG_TAG "hy300-sensors"

#include "Sensors.h"

#include <android-base/logging.h>

namespace hy300::sensors {

using ndk::ScopedAStatus;

namespace {

ScopedAStatus unsupported() {
    return ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
}

}  // namespace

Sensors::~Sensors() {
    sensors_.clear();
    std::lock_guard lock(writeMutex_);
    deleteEventFlagLocked();
}

void Sensors::addAccelerometer(std::unique_ptr<AccelReader> reader,
                               std::unique_ptr<AccelControl> control) {
    const int32_t handle = nextHandle_++;
    sensors_[handle] = std::make_unique<AccelSensor>(
            handle, std::move(reader), std::move(control),
            [this](const std::vector<Event>& events) { postEvents(events); });
}

void Sensors::postEvents(const std::vector<Event>& events) {
    std::lock_guard lock(writeMutex_);
    if (!eventQueue_ || events.empty() || !eventQueue_->write(events.data(), events.size())) {
        return;
    }
    if (eventFlag_ != nullptr) {
        eventFlag_->wake(static_cast<uint32_t>(EVENT_QUEUE_FLAG_BITS_READ_AND_PROCESS));
    }
}

void Sensors::deleteEventFlagLocked() {
    if (eventFlag_ != nullptr) {
        android::hardware::EventFlag::deleteEventFlag(&eventFlag_);
    }
}

ScopedAStatus Sensors::activate(int32_t handle, bool enabled) {
    const auto it = sensors_.find(handle);
    if (it == sensors_.end()) {
        return ScopedAStatus::fromExceptionCode(EX_ILLEGAL_ARGUMENT);
    }
    it->second->activate(enabled);
    return ScopedAStatus::ok();
}

ScopedAStatus Sensors::batch(int32_t handle, int64_t samplingPeriodNs,
                             int64_t /* maxReportLatencyNs */) {
    const auto it = sensors_.find(handle);
    if (it == sensors_.end()) {
        return ScopedAStatus::fromExceptionCode(EX_ILLEGAL_ARGUMENT);
    }
    it->second->batch(samplingPeriodNs);
    return ScopedAStatus::ok();
}

ScopedAStatus Sensors::configDirectReport(int32_t, int32_t, RateLevel, int32_t* result) {
    *result = EX_UNSUPPORTED_OPERATION;
    return unsupported();
}

ScopedAStatus Sensors::flush(int32_t handle) {
    const auto it = sensors_.find(handle);
    if (it == sensors_.end()) {
        return ScopedAStatus::fromExceptionCode(EX_ILLEGAL_ARGUMENT);
    }
    return it->second->flush();
}

ScopedAStatus Sensors::getSensorsList(std::vector<SensorInfo>* result) {
    result->clear();
    for (const auto& [_, sensor] : sensors_) {
        result->push_back(sensor->getSensorInfo());
    }
    return ScopedAStatus::ok();
}

ScopedAStatus Sensors::initialize(
        const MQDescriptor<Event>& eventQueueDescriptor,
        const MQDescriptor<int32_t>& wakeLockDescriptor,
        const std::shared_ptr<aidl::android::hardware::sensors::ISensorsCallback>& callback) {
    LOG(INFO) << "initialize: " << sensors_.size() << " sensor(es)";
    for (const auto& [_, sensor] : sensors_) {
        sensor->activate(false);
    }
    callback_ = callback;

    std::lock_guard lock(writeMutex_);
    eventQueue_ = std::make_unique<android::AidlMessageQueue<Event, SynchronizedReadWrite>>(
            eventQueueDescriptor, true /* resetPointers */);
    deleteEventFlagLocked();
    const bool flagCreated = android::hardware::EventFlag::createEventFlag(
                                     eventQueue_->getEventFlagWord(), &eventFlag_) == android::OK;
    // Só sensores que não acordam: a fila de wake lock fica aberta, mas nunca recebe nada.
    wakeLockQueue_ = std::make_unique<android::AidlMessageQueue<int32_t, SynchronizedReadWrite>>(
            wakeLockDescriptor, true /* resetPointers */);
    if (!callback_ || !flagCreated || !eventQueue_->isValid() || !wakeLockQueue_->isValid()) {
        return ScopedAStatus::fromExceptionCode(EX_ILLEGAL_ARGUMENT);
    }
    return ScopedAStatus::ok();
}

ScopedAStatus Sensors::injectSensorData(const Event&) {
    return ScopedAStatus::fromServiceSpecificError(ERROR_BAD_VALUE);
}

ScopedAStatus Sensors::registerDirectChannel(const SharedMemInfo&, int32_t* result) {
    *result = EX_UNSUPPORTED_OPERATION;
    return unsupported();
}

ScopedAStatus Sensors::setOperationMode(OperationMode mode) {
    if (mode != OperationMode::NORMAL) {
        return ScopedAStatus::fromServiceSpecificError(ERROR_BAD_VALUE);
    }
    for (const auto& [_, sensor] : sensors_) {
        sensor->setOperationMode(mode);
    }
    return ScopedAStatus::ok();
}

ScopedAStatus Sensors::unregisterDirectChannel(int32_t) {
    return unsupported();
}

}  // namespace hy300::sensors
