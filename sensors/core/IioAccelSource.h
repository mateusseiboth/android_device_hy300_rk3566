/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <filesystem>
#include <optional>
#include <string_view>

#include "AccelSource.h"

namespace hy300::sensors {

// /sys/bus/iio/devices/iio:deviceN cujo "name" é `name`.
std::optional<std::filesystem::path> findIioDevice(const std::filesystem::path& root,
                                                   std::string_view name);

// Lê in_accel_{x,y,z}_raw por sysfs a cada amostra (m/s² = (raw + offset) * scale, com a escala
// por eixo valendo sobre a comum). O kernel do driver é quem decide a taxa interna.
class IioAccelSource : public AccelSource {
  public:
    explicit IioAccelSource(std::filesystem::path device);

    std::optional<Vec3> read() override;
    bool isScaled() const override { return true; }

  private:
    std::optional<float> readAxis(char axis) const;

    std::filesystem::path device_;
};

}  // namespace hy300::sensors
