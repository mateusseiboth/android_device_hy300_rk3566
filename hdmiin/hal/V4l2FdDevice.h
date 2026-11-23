/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <android-base/unique_fd.h>

#include <string>

#include "V4l2Device.h"

namespace hy300::hdmiin {

// /dev/videoN de verdade, aberto sem bloquear (o DQBUF devolve EAGAIN quando a fila esvazia).
class V4l2FdDevice : public V4l2Device {
  public:
    explicit V4l2FdDevice(const std::string& path);
    bool isOpen() const { return fd_.get() >= 0; }
    int xioctl(unsigned long request, void* arg) override;
    bool waitReadable(int timeoutMs) override;

  private:
    android::base::unique_fd fd_;
};

}  // namespace hy300::hdmiin
