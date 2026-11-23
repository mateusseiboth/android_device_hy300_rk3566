/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#include "IioAccelSource.h"

#include <cmath>
#include <cstdlib>
#include <fstream>
#include <string>
#include <system_error>

namespace hy300::sensors {
namespace {

namespace fs = std::filesystem;

std::optional<std::string> readLine(const fs::path& path) {
    std::ifstream file(path);
    std::string line;
    if (!file || !std::getline(file, line)) {
        return std::nullopt;
    }
    return line;
}

std::optional<float> readNumber(const fs::path& path) {
    const auto line = readLine(path);
    if (!line) {
        return std::nullopt;
    }
    char* end = nullptr;
    const float value = std::strtof(line->c_str(), &end);
    if (end == line->c_str() || !std::isfinite(value)) {
        return std::nullopt;
    }
    return value;
}

}  // namespace

std::optional<fs::path> findIioDevice(const fs::path& root, std::string_view name) {
    std::error_code error;
    for (const auto& entry : fs::directory_iterator(root, error)) {
        if (readLine(entry.path() / "name") == name) {
            return entry.path();
        }
    }
    return std::nullopt;
}

IioAccelSource::IioAccelSource(fs::path device) : device_(std::move(device)) {}

std::optional<float> IioAccelSource::readAxis(char axis) const {
    const std::string prefix = std::string("in_accel_") + axis;
    const auto raw = readNumber(device_ / (prefix + "_raw"));
    if (!raw) {
        return std::nullopt;
    }
    const float offset = readNumber(device_ / (prefix + "_offset"))
                                 .value_or(readNumber(device_ / "in_accel_offset").value_or(0.f));
    const float scale = readNumber(device_ / (prefix + "_scale"))
                                .value_or(readNumber(device_ / "in_accel_scale").value_or(1.f));
    return (*raw + offset) * scale;
}

std::optional<Vec3> IioAccelSource::read() {
    const auto x = readAxis('x');
    const auto y = readAxis('y');
    const auto z = readAxis('z');
    if (!x || !y || !z) {
        return std::nullopt;
    }
    return Vec3{*x, *y, *z};
}

}  // namespace hy300::sensors
