/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#include "InputAccelSource.h"

#include <fcntl.h>
#include <linux/input.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include <fstream>
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

// Valor atual de um eixo, para não esperar o primeiro evento (só num evdev de verdade).
std::optional<float> readAbsolute(int fd, unsigned code) {
    input_absinfo info{};
    if (ioctl(fd, EVIOCGABS(code), &info) != 0) {
        return std::nullopt;
    }
    return static_cast<float>(info.value);
}

}  // namespace

std::optional<std::string> findInputEvent(const fs::path& root, std::string_view name) {
    std::error_code error;
    for (const auto& entry : fs::directory_iterator(root, error)) {
        const std::string node = entry.path().filename().string();
        if (node.rfind("event", 0) == 0 && readLine(entry.path() / "device" / "name") == name) {
            return node;
        }
    }
    return std::nullopt;
}

InputAccelSource::InputAccelSource(int fd) : fd_(fd) {
    fcntl(fd_, F_SETFL, fcntl(fd_, F_GETFL) | O_NONBLOCK);
    const auto x = readAbsolute(fd_, ABS_X);
    const auto y = readAbsolute(fd_, ABS_Y);
    const auto z = readAbsolute(fd_, ABS_Z);
    if (x && y && z) {
        pending_ = {*x, *y, *z};
        last_ = pending_;
    }
}

InputAccelSource::~InputAccelSource() {
    close(fd_);
}

void InputAccelSource::handleEvent(unsigned type, unsigned code, int value) {
    if (type == EV_SYN && code == SYN_DROPPED) {
        dropping_ = true;
        return;
    }
    if (type == EV_SYN && code == SYN_REPORT) {
        if (!dropping_) {
            last_ = pending_;
        }
        dropping_ = false;
        return;
    }
    if (type != EV_ABS || dropping_) {
        return;
    }
    const float v = static_cast<float>(value);
    if (code == ABS_X) pending_.x = v;
    if (code == ABS_Y) pending_.y = v;
    if (code == ABS_Z) pending_.z = v;
}

std::optional<Vec3> InputAccelSource::read() {
    input_event events[32];
    for (;;) {
        const ssize_t bytes = ::read(fd_, events, sizeof(events));
        if (bytes <= 0) {
            break;
        }
        const size_t count = static_cast<size_t>(bytes) / sizeof(input_event);
        for (size_t i = 0; i < count; ++i) {
            handleEvent(events[i].type, events[i].code, events[i].value);
        }
    }
    return last_;
}

}  // namespace hy300::sensors
