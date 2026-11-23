/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <memory>
#include <optional>

#include "AccelConfig.h"
#include "AccelSource.h"

namespace hy300::sensors {

// Amostra em m/s² nos eixos do Android: escala (para fontes cruas) e troca de eixos.
class AccelReader {
  public:
    AccelReader(std::unique_ptr<AccelSource> source, AccelConfig config);

    std::optional<Vec3> read();

  private:
    std::unique_ptr<AccelSource> source_;
    AccelConfig config_;
};

}  // namespace hy300::sensors
