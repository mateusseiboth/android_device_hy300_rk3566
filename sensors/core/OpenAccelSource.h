/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <filesystem>
#include <memory>

#include "AccelConfig.h"
#include "AccelSource.h"

namespace hy300::sensors {

struct SysfsRoots {
    std::filesystem::path iio = "/sys/bus/iio/devices";
    std::filesystem::path input = "/sys/class/input";
    std::filesystem::path devInput = "/dev/input";
};

// Abre a fonte do backend configurado; nullptr se o dispositivo não existe (o HAL sobe sem
// sensores, e o app mostra o automático como indisponível).
std::unique_ptr<AccelSource> openAccelSource(const AccelConfig& config,
                                             const SysfsRoots& roots = SysfsRoots{});

// Controle de liga/desliga do backend (só o gsensor da Rockchip tem); nullptr se não precisa.
std::unique_ptr<AccelControl> openAccelControl(const AccelConfig& config);

}  // namespace hy300::sensors
