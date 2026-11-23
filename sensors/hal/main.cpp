/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#define LOG_TAG "hy300-sensors"

#include <android-base/logging.h>
#include <android-base/properties.h>
#include <android/binder_manager.h>
#include <android/binder_process.h>

#include "AccelConfig.h"
#include "OpenAccelSource.h"
#include "Sensors.h"

using hy300::sensors::AccelReader;
using hy300::sensors::Sensors;

int main() {
    ABinderProcess_setThreadPoolMaxThreadCount(0);

    const auto config = hy300::sensors::buildAccelConfig(
            [](const char* name) { return android::base::GetProperty(name, ""); });
    auto sensors = ndk::SharedRefBase::make<Sensors>();
    if (auto source = hy300::sensors::openAccelSource(config)) {
        sensors->addAccelerometer(std::make_unique<AccelReader>(std::move(source), config),
                                  hy300::sensors::openAccelControl(config));
    } else {
        // Sem o driver no kernel o serviço sobe vazio: o framework precisa do HAL declarado.
        LOG(WARNING) << "acelerômetro \"" << config.device << "\" não encontrado";
    }

    const std::string instance = std::string(Sensors::descriptor) + "/default";
    CHECK_EQ(AServiceManager_addService(sensors->asBinder().get(), instance.c_str()), STATUS_OK);
    ABinderProcess_joinThreadPool();
    return EXIT_FAILURE;
}
