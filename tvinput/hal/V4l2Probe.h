/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <android-base/unique_fd.h>

#include <string>

#include "HdmiInCore.h"

namespace hy300::tvinput {

// Lê o estado do sinal no subdev V4L2 do RK628: 5 V do cabo (V4L2_CID_DV_RX_POWER_PRESENT) e a
// resolução travada (VIDIOC_SUBDEV_QUERY_DV_TIMINGS). Reabre o nó se ele sumir.
class V4l2Probe {
  public:
    explicit V4l2Probe(std::string subdevPath);
    SignalState read();

  private:
    std::string path_;
    android::base::unique_fd fd_;
};

}  // namespace hy300::tvinput
