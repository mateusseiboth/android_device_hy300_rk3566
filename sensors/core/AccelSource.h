/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <optional>

namespace hy300::sensors {

struct Vec3 {
    float x = 0.f;
    float y = 0.f;
    float z = 0.f;
};

// De onde vêm as amostras do acelerômetro (IIO, input do kernel). read() nunca bloqueia:
// devolve a amostra mais recente ou nada, se ainda não houver.
class AccelSource {
  public:
    virtual ~AccelSource() = default;
    virtual std::optional<Vec3> read() = 0;
    // true quando a fonte já entrega m/s² (IIO com in_accel_scale); false para valores crus.
    virtual bool isScaled() const = 0;
};

// Liga e desliga a medição no kernel, quando o driver exige (gsensor da Rockchip).
class AccelControl {
  public:
    virtual ~AccelControl() = default;
    virtual bool start(int periodMs) = 0;
    virtual void stop() = 0;
};

}  // namespace hy300::sensors
