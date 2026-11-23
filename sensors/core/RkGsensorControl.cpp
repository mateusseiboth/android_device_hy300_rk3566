/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#include "RkGsensorControl.h"

#include <fcntl.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include <utility>

namespace hy300::sensors {
namespace {

// include/linux/sensor-dev.h do kernel Rockchip.
constexpr unsigned kGsensorMagic = 'a';
constexpr unsigned long kGsensorClose = _IO(kGsensorMagic, 0x02);
constexpr unsigned long kGsensorStart = _IO(kGsensorMagic, 0x03);
constexpr unsigned long kGsensorSetRate = _IOW(kGsensorMagic, 0x10, short);

}  // namespace

RkGsensorControl::RkGsensorControl(std::string path) : path_(std::move(path)) {}

RkGsensorControl::~RkGsensorControl() {
    stop();
}

bool RkGsensorControl::start(int periodMs) {
    if (fd_ < 0) {
        fd_ = open(path_.c_str(), O_RDWR | O_CLOEXEC);
    }
    if (fd_ < 0) {
        return false;
    }
    short rate = static_cast<short>(periodMs);
    ioctl(fd_, kGsensorSetRate, &rate);
    return ioctl(fd_, kGsensorStart) == 0;
}

void RkGsensorControl::stop() {
    if (fd_ < 0) {
        return;
    }
    ioctl(fd_, kGsensorClose);
    close(fd_);
    fd_ = -1;
}

}  // namespace hy300::sensors
