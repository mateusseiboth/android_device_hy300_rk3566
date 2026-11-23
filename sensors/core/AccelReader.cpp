/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#include "AccelReader.h"

#include <utility>

namespace hy300::sensors {

AccelReader::AccelReader(std::unique_ptr<AccelSource> source, AccelConfig config)
    : source_(std::move(source)), config_(std::move(config)) {}

std::optional<Vec3> AccelReader::read() {
    const auto raw = source_->read();
    if (!raw) {
        return std::nullopt;
    }
    const float scale = source_->isScaled() ? 1.f : config_.scale;
    const Vec3 scaled = {raw->x * scale, raw->y * scale, raw->z * scale};
    return applyAxisMap(config_.axes, scaled);
}

}  // namespace hy300::sensors
