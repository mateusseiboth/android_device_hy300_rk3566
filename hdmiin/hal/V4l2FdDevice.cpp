/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#include "V4l2FdDevice.h"

#include <fcntl.h>
#include <poll.h>
#include <sys/ioctl.h>

#include <cerrno>

namespace hy300::hdmiin {

V4l2FdDevice::V4l2FdDevice(const std::string& path)
    : fd_(open(path.c_str(), O_RDWR | O_NONBLOCK | O_CLOEXEC)) {}

int V4l2FdDevice::xioctl(unsigned long request, void* arg) {
    int result;
    do {
        result = ioctl(fd_.get(), request, arg);
    } while (result != 0 && errno == EINTR);
    return result;
}

bool V4l2FdDevice::waitReadable(int timeoutMs) {
    pollfd fd{.fd = fd_.get(), .events = POLLIN, .revents = 0};
    return poll(&fd, 1, timeoutMs) > 0 && (fd.revents & POLLIN) != 0;
}

}  // namespace hy300::hdmiin
