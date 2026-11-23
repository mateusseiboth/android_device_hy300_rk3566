/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include "PreviewPump.h"

namespace hy300::hdmiin {

// NV12 da captura para RGBA 8888 da janela pela RGA (librga, API por fd), com escala, síncrono.
class RgaBlitter : public Blitter {
  public:
    bool blit(int srcFd, const CaptureFormat& src, const GraphicTarget& dst) override;
};

}  // namespace hy300::hdmiin
