/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#include "HdmiInCore.h"

#include <charconv>
#include <fstream>
#include <system_error>

namespace hy300::tvinput {
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

std::optional<int> parsePositive(const std::string& text) {
    int value = 0;
    const char* end = text.data() + text.size();
    const auto [ptr, error] = std::from_chars(text.data(), end, value);
    if (text.empty() || error != std::errc() || ptr != end || value <= 0) {
        return std::nullopt;
    }
    return value;
}

void assignIfSet(std::string& target, const std::string& value) {
    if (!value.empty()) {
        target = value;
    }
}

}  // namespace

HdmiInConfig buildHdmiInConfig(const PropertyGetter& get) {
    HdmiInConfig config;
    assignIfSet(config.videoName, get("ro.vendor.hy300.hdmiin.video"));
    assignIfSet(config.subdevName, get("ro.vendor.hy300.hdmiin.subdev"));
    assignIfSet(config.audioAddress, get("ro.vendor.hy300.hdmiin.audio_address"));
    config.pollMs = parsePositive(get("ro.vendor.hy300.hdmiin.poll_ms")).value_or(config.pollMs);
    return config;
}

std::optional<std::string> findV4l2Node(const fs::path& root, std::string_view kind,
                                        std::string_view name) {
    std::error_code error;
    for (const auto& entry : fs::directory_iterator(root, error)) {
        const std::string node = entry.path().filename().string();
        const bool isKind = node.rfind(kind, 0) == 0 &&
                node.find_first_not_of("0123456789", kind.size()) == std::string::npos;
        const auto nodeName = readLine(entry.path() / "name");
        if (isKind && nodeName && nodeName->find(name) != std::string::npos) {
            return node;
        }
    }
    return std::nullopt;
}

Cable toCable(const SignalState& state) {
    return state.cablePresent ? Cable::kConnected : Cable::kDisconnected;
}

std::vector<StreamConfig> buildStreamConfigs(const SignalState& state) {
    if (!state.timing) {
        return {};
    }
    return {StreamConfig{kStreamId, state.timing->width, state.timing->height}};
}

bool HdmiInTracker::update(const SignalState& state) {
    current_ = state;
    if (reported_ == state) {
        return false;
    }
    reported_ = state;
    return true;
}

std::vector<int32_t> buildSidebandInts(const Size& size, uint32_t fourcc) {
    return {kSidebandMagic, size.width, size.height, static_cast<int32_t>(fourcc)};
}

}  // namespace hy300::tvinput
