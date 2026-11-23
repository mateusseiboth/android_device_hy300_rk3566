/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <string>

#include "AccelSource.h"

namespace hy300::sensors {

// Framework "gsensor" do kernel Rockchip (drivers/input/sensors): o driver só lê o chip
// depois de GSENSOR_IOCTL_START no nó de controle (/dev/mma8452_daemon), e a taxa vem de
// GSENSOR_IOCTL_APP_SET_RATE (ms). É o que o sensors.rk30board da fábrica fazia.
class RkGsensorControl : public AccelControl {
  public:
    explicit RkGsensorControl(std::string path);
    ~RkGsensorControl() override;

    bool start(int periodMs) override;
    void stop() override;

  private:
    std::string path_;
    int fd_ = -1;
};

}  // namespace hy300::sensors
