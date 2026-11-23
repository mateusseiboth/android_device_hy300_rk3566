/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <aidl/android/hardware/sensors/BnSensors.h>

#include <atomic>
#include <condition_variable>
#include <functional>
#include <memory>
#include <mutex>
#include <thread>
#include <vector>

#include "AccelReader.h"
#include "AccelSource.h"

namespace hy300::sensors {

// Acelerômetro contínuo (não acorda o aparelho): uma thread lê a fonte no período pedido
// pelo framework e entrega os eventos. A medição no kernel só fica ligada com o sensor ativo.
class AccelSensor {
  public:
    using Event = aidl::android::hardware::sensors::Event;
    using SensorInfo = aidl::android::hardware::sensors::SensorInfo;
    using OperationMode = aidl::android::hardware::sensors::ISensors::OperationMode;
    using EventSink = std::function<void(const std::vector<Event>&)>;

    AccelSensor(int32_t handle, std::unique_ptr<AccelReader> reader,
                std::unique_ptr<AccelControl> control, EventSink sink);
    ~AccelSensor();

    const SensorInfo& getSensorInfo() const { return info_; }
    void activate(bool enable);
    void batch(int64_t samplingPeriodNs);
    ndk::ScopedAStatus flush();
    void setOperationMode(OperationMode mode);

  private:
    void run();
    void postSample();

    SensorInfo info_;
    std::unique_ptr<AccelReader> reader_;
    std::unique_ptr<AccelControl> control_;
    EventSink sink_;

    std::mutex mutex_;
    std::condition_variable wake_;
    bool enabled_ = false;
    bool stop_ = false;
    int64_t periodNs_;
    OperationMode mode_ = OperationMode::NORMAL;
    std::thread thread_;
};

}  // namespace hy300::sensors
