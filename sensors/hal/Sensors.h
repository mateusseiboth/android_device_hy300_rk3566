/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <aidl/android/hardware/common/fmq/SynchronizedReadWrite.h>
#include <aidl/android/hardware/sensors/BnSensors.h>
#include <android-base/thread_annotations.h>
// O libfmq não compila limpo com -Wconversion (sinal e 64->32 nos templates do cabeçalho); o
// código deste HAL continua com -Wconversion -Werror.
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wconversion"
#pragma clang diagnostic ignored "-Wsign-conversion"
#pragma clang diagnostic ignored "-Wshorten-64-to-32"
#include <fmq/AidlMessageQueue.h>
#include <fmq/EventFlag.h>
#pragma clang diagnostic pop

#include <map>
#include <memory>
#include <mutex>
#include <vector>

#include "AccelSensor.h"

namespace hy300::sensors {

// HAL de sensores AIDL mínimo do HY300: só sensores contínuos, sem acordar o aparelho, sem
// canal direto nem injeção. Os eventos vão pela FMQ que o framework entrega no initialize().
class Sensors : public aidl::android::hardware::sensors::BnSensors {
  public:
    using Event = aidl::android::hardware::sensors::Event;
    using SensorInfo = aidl::android::hardware::sensors::SensorInfo;
    using SynchronizedReadWrite = aidl::android::hardware::common::fmq::SynchronizedReadWrite;
    template <typename T>
    using MQDescriptor = aidl::android::hardware::common::fmq::MQDescriptor<T, SynchronizedReadWrite>;

    Sensors() = default;
    ~Sensors() override;

    // Liga o acelerômetro ao HAL; chamar antes de registrar o serviço.
    void addAccelerometer(std::unique_ptr<AccelReader> reader,
                          std::unique_ptr<AccelControl> control);

    ndk::ScopedAStatus activate(int32_t handle, bool enabled) override;
    ndk::ScopedAStatus batch(int32_t handle, int64_t samplingPeriodNs,
                             int64_t maxReportLatencyNs) override;
    ndk::ScopedAStatus configDirectReport(int32_t handle, int32_t channelHandle,
                                          RateLevel rate, int32_t* result) override;
    ndk::ScopedAStatus flush(int32_t handle) override;
    ndk::ScopedAStatus getSensorsList(std::vector<SensorInfo>* result) override;
    ndk::ScopedAStatus initialize(
            const MQDescriptor<Event>& eventQueueDescriptor,
            const MQDescriptor<int32_t>& wakeLockDescriptor,
            const std::shared_ptr<aidl::android::hardware::sensors::ISensorsCallback>& callback)
            override;
    ndk::ScopedAStatus injectSensorData(const Event& event) override;
    ndk::ScopedAStatus registerDirectChannel(const SharedMemInfo& mem, int32_t* result) override;
    ndk::ScopedAStatus setOperationMode(OperationMode mode) override;
    ndk::ScopedAStatus unregisterDirectChannel(int32_t channelHandle) override;

  private:
    void postEvents(const std::vector<Event>& events);
    void deleteEventFlagLocked() REQUIRES(writeMutex_);

    std::map<int32_t, std::unique_ptr<AccelSensor>> sensors_;
    int32_t nextHandle_ = 1;

    std::mutex writeMutex_;
    std::unique_ptr<android::AidlMessageQueue<Event, SynchronizedReadWrite>> eventQueue_
            GUARDED_BY(writeMutex_);
    std::unique_ptr<android::AidlMessageQueue<int32_t, SynchronizedReadWrite>> wakeLockQueue_
            GUARDED_BY(writeMutex_);
    android::hardware::EventFlag* eventFlag_ GUARDED_BY(writeMutex_) = nullptr;
    std::shared_ptr<aidl::android::hardware::sensors::ISensorsCallback> callback_;
};

}  // namespace hy300::sensors
