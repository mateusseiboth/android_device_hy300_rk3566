/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <cstdint>
#include <optional>

#include "CaptureStream.h"

namespace hy300::hdmiin {

// Buffer da janela (Surface do app) para onde a RGA escreve: dma-buf e geometria.
struct GraphicTarget {
    int fd = -1;
    uint32_t width = 0;
    uint32_t height = 0;
    uint32_t stride = 0;  // em pixels
    void* token = nullptr;  // ANativeWindowBuffer*, para devolver à janela
};

class FrameSink {
  public:
    virtual ~FrameSink() = default;
    virtual std::optional<GraphicTarget> dequeue() = 0;
    virtual void queue(const GraphicTarget& target) = 0;
    virtual void cancel(const GraphicTarget& target) = 0;
};

// Cópia de hardware (RGA): NV12 da captura para o formato da janela, com escala.
class Blitter {
  public:
    virtual ~Blitter() = default;
    virtual bool blit(int srcFd, const CaptureFormat& src, const GraphicTarget& dst) = 0;
};

// Uma volta do laço da prévia: o quadro mais novo da captura vai para um buffer da janela pela
// RGA, e o buffer da captura volta ao driver na hora. Sem quadro novo, não mexe na janela.
class PreviewPump {
  public:
    enum class Step { kFrame, kNoFrame, kNoTarget, kBlitFailed };

    PreviewPump(CaptureStream& stream, FrameSink& sink, Blitter& blitter);
    Step runOnce(int timeoutMs);

  private:
    CaptureStream& stream_;
    FrameSink& sink_;
    Blitter& blitter_;
};

}  // namespace hy300::hdmiin
