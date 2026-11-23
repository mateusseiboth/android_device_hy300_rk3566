/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#include "V4l2Probe.h"

#include <fcntl.h>
#include <linux/v4l2-controls.h>
#include <linux/v4l2-subdev.h>
#include <linux/videodev2.h>
#include <sys/ioctl.h>

namespace hy300::tvinput {

V4l2Probe::V4l2Probe(std::string subdevPath) : path_(std::move(subdevPath)) {}

SignalState V4l2Probe::read() {
    if (fd_.get() < 0) {
        fd_.reset(open(path_.c_str(), O_RDWR | O_CLOEXEC));
    }
    SignalState state;
    if (fd_.get() < 0) {
        return state;
    }
    v4l2_control power{};
    power.id = V4L2_CID_DV_RX_POWER_PRESENT;
    state.cablePresent = ioctl(fd_.get(), VIDIOC_G_CTRL, &power) == 0 && power.value != 0;

    v4l2_dv_timings timings{};
    if (ioctl(fd_.get(), VIDIOC_SUBDEV_QUERY_DV_TIMINGS, &timings) == 0 &&
        timings.type == V4L2_DV_BT_656_1120 && timings.bt.width > 0 && timings.bt.height > 0) {
        state.timing = Size{static_cast<int32_t>(timings.bt.width),
                            static_cast<int32_t>(timings.bt.height)};
    }
    return state;
}

}  // namespace hy300::tvinput
