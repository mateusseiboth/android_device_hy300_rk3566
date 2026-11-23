/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#include "AccelConfig.h"

#include <cmath>
#include <cstdlib>
#include <map>

namespace hy300::sensors {
namespace {

std::string_view trim(std::string_view text) {
    const auto first = text.find_first_not_of(" \t");
    if (first == std::string_view::npos) {
        return {};
    }
    return text.substr(first, text.find_last_not_of(" \t") - first + 1);
}

std::optional<AxisSource> parseAxis(std::string_view text) {
    const std::string_view axis = trim(text);
    const bool negative = !axis.empty() && axis.front() == '-';
    const std::string_view name = negative ? axis.substr(1) : axis;
    static const std::map<std::string_view, int> kIndexes = {{"x", 0}, {"y", 1}, {"z", 2}};
    const auto it = kIndexes.find(name);
    if (it == kIndexes.end()) {
        return std::nullopt;
    }
    return AxisSource{it->second, negative ? -1.f : 1.f};
}

std::optional<Backend> parseBackend(std::string_view text) {
    static const std::map<std::string_view, Backend> kBackends = {
            {"rk-gsensor", Backend::kRockchipGsensor},
            {"input", Backend::kInput},
            {"iio", Backend::kIio},
    };
    const auto it = kBackends.find(trim(text));
    return it == kBackends.end() ? std::nullopt : std::optional<Backend>(it->second);
}

std::optional<float> parsePositive(const std::string& text) {
    char* end = nullptr;
    const float value = std::strtof(text.c_str(), &end);
    if (text.empty() || *end != '\0' || !std::isfinite(value) || value <= 0.f) {
        return std::nullopt;
    }
    return value;
}

}  // namespace

std::optional<AxisMap> parseAxisMap(std::string_view text) {
    AxisMap map;
    std::array<bool, 3> used = {false, false, false};
    size_t start = 0;
    for (size_t i = 0; i < map.size(); ++i) {
        const size_t comma = text.find(',', start);
        const bool isLast = i + 1 == map.size();
        if (isLast != (comma == std::string_view::npos)) {
            return std::nullopt;
        }
        const auto axis = parseAxis(text.substr(start, comma - start));
        if (!axis || used[static_cast<size_t>(axis->index)]) {
            return std::nullopt;
        }
        used[static_cast<size_t>(axis->index)] = true;
        map[i] = *axis;
        start = comma + 1;
    }
    return map;
}

Vec3 applyAxisMap(const AxisMap& map, const Vec3& in) {
    const std::array<float, 3> values = {in.x, in.y, in.z};
    const auto pick = [&](const AxisSource& source) {
        return source.sign * values[static_cast<size_t>(source.index)];
    };
    return {pick(map[0]), pick(map[1]), pick(map[2])};
}

AccelConfig buildAccelConfig(const PropertyGetter& get) {
    AccelConfig config;
    if (const auto backend = parseBackend(get("ro.vendor.hy300.accel.backend"))) {
        config.backend = *backend;
    }
    if (const std::string device = get("ro.vendor.hy300.accel.device"); !device.empty()) {
        config.device = device;
    }
    if (const std::string control = get("ro.vendor.hy300.accel.control"); !control.empty()) {
        config.control = control;
    }
    if (const auto scale = parsePositive(get("ro.vendor.hy300.accel.scale"))) {
        config.scale = *scale;
    }
    if (const auto axes = parseAxisMap(get("ro.vendor.hy300.accel.axes"))) {
        config.axes = *axes;
    }
    return config;
}

}  // namespace hy300::sensors
