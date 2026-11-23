/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <cstdint>
#include <optional>
#include <vector>

#include "V4l2Device.h"

// Captura da entrada HDMI do HY300: RK628 -> csi2-dphy0 -> rkisp, /dev/videoN multiplanar.
// Os buffers são do driver (MMAP) e saem como dma-buf (VIDIOC_EXPBUF): a RGA lê direto deles,
// sem cópia pela CPU.
namespace hy300::hdmiin {

struct CaptureSize {
    uint32_t width = 0;
    uint32_t height = 0;
    bool operator==(const CaptureSize&) const = default;
};

struct CaptureFormat {
    uint32_t width = 0;
    uint32_t height = 0;
    uint32_t fourcc = 0;
    uint32_t bytesPerLine = 0;
    uint32_t sizeImage = 0;
};

// A fonte trocou de resolução (ou perdeu o sinal): a captura tem de recomeçar.
bool needsRestart(const CaptureSize& configured, const std::optional<CaptureSize>& signal);

class CaptureStream {
  public:
    explicit CaptureStream(V4l2Device& device);
    ~CaptureStream();

    CaptureStream(const CaptureStream&) = delete;
    CaptureStream& operator=(const CaptureStream&) = delete;

    // NV12 multiplanar (1 plano) no tamanho do sinal, bufferCount buffers MMAP exportados.
    bool configure(uint32_t width, uint32_t height, uint32_t bufferCount);
    bool start();
    void stop();

    // Tira da fila todos os quadros prontos, devolve os antigos ao driver e fica com o mais novo.
    std::optional<uint32_t> acquireLatest(int timeoutMs);
    bool release(uint32_t index);

    const CaptureFormat& format() const { return format_; }
    int dmabuf(uint32_t index) const;

  private:
    bool queue(uint32_t index);
    std::optional<uint32_t> dequeue();
    void closeBuffers();

    V4l2Device& device_;
    CaptureFormat format_;
    std::vector<int> dmabufs_;
    bool streaming_ = false;
};

}  // namespace hy300::hdmiin
