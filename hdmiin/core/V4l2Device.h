/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

namespace hy300::hdmiin {

// As duas operações do nó de captura que a lógica usa; o teste troca por um V4L2 falso.
class V4l2Device {
  public:
    virtual ~V4l2Device() = default;
    // ioctl com repetição em EINTR; -1 e errno como o ioctl.
    virtual int xioctl(unsigned long request, void* arg) = 0;
    // Espera um quadro pronto (POLLIN) até timeoutMs.
    virtual bool waitReadable(int timeoutMs) = 0;
};

}  // namespace hy300::hdmiin
