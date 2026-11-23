/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <array>
#include <functional>
#include <optional>
#include <string>
#include <string_view>

#include "AccelSource.h"

namespace hy300::sensors {

// Qual interface do kernel o HAL usa. O driver do SC7A20 do kernel Rockchip (GS_SC7A20) é do
// framework "gsensor": input "gsensor" com 1 g = 16384, ligado por ioctl em
// /dev/mma8452_daemon. Um driver IIO (st_accel/lis3dh) ou um input comum também servem.
enum class Backend { kRockchipGsensor, kInput, kIio };

// Cada eixo de saída vem de um eixo de entrada, com sinal.
struct AxisSource {
    int index = 0;  // 0 = x, 1 = y, 2 = z
    float sign = 1.f;
};
using AxisMap = std::array<AxisSource, 3>;

struct AccelConfig {
    Backend backend = Backend::kRockchipGsensor;
    std::string device = "gsensor";              // nome do input ou do dispositivo IIO
    std::string control = "/dev/mma8452_daemon";  // só para o gsensor da Rockchip
    float scale = 9.80665f / 16384.f;             // m/s² por unidade crua
    AxisMap axes = {AxisSource{0, 1.f}, AxisSource{1, 1.f}, AxisSource{2, 1.f}};
};

using PropertyGetter = std::function<std::string(const char* name)>;

// "x,y,z", "-y,x,z" etc.: cada eixo de entrada uma vez só.
std::optional<AxisMap> parseAxisMap(std::string_view text);

Vec3 applyAxisMap(const AxisMap& map, const Vec3& in);

// Props ro.vendor.hy300.accel.{backend,device,control,scale,axes}; valor vazio ou inválido
// fica no padrão (o SC7A20 do HY300 pelo gsensor da Rockchip).
AccelConfig buildAccelConfig(const PropertyGetter& get);

}  // namespace hy300::sensors
