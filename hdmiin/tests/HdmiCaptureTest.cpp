/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 *
 * Testes da captura da entrada HDMI no host, com o V4L2 falso (FakeV4l2.h).
 */

#include <gtest/gtest.h>

#include <algorithm>
#include <optional>
#include <vector>

#include "CaptureStream.h"
#include "FakeV4l2.h"
#include "PreviewPump.h"

namespace hy300::hdmiin {
namespace {

constexpr uint32_t kBuffers = 4;

class CaptureStreamTest : public ::testing::Test {
  protected:
    FakeV4l2 device;
    CaptureStream stream{device};

    void startStream() {
        ASSERT_TRUE(stream.configure(1920, 1080, kBuffers));
        ASSERT_TRUE(stream.start());
    }
};

TEST_F(CaptureStreamTest, configuresMultiplanarNv12AndExportsEveryBuffer) {
    ASSERT_TRUE(stream.configure(1920, 1080, kBuffers));
    EXPECT_EQ(device.lastFormat.type, V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE);
    EXPECT_EQ(device.lastFormat.fmt.pix_mp.width, 1920U);
    EXPECT_EQ(device.lastFormat.fmt.pix_mp.height, 1080U);
    EXPECT_EQ(stream.format().fourcc, static_cast<uint32_t>(V4L2_PIX_FMT_NV12));
    EXPECT_EQ(stream.format().bytesPerLine, 1920U);
    EXPECT_EQ(device.bufferCount, kBuffers);
    for (uint32_t i = 0; i < kBuffers; ++i) {
        EXPECT_GE(stream.dmabuf(i), 0);
    }
}

TEST_F(CaptureStreamTest, refusesAFormatOtherThanNv12) {
    device.acceptedFourcc = V4L2_PIX_FMT_NV16;
    EXPECT_FALSE(stream.configure(1920, 1080, kBuffers));
}

TEST_F(CaptureStreamTest, startQueuesAllBuffersAndStreams) {
    startStream();
    EXPECT_TRUE(device.streaming);
    EXPECT_EQ(device.queued.size(), kBuffers);
}

TEST_F(CaptureStreamTest, nothingReadyGivesNoFrame) {
    startStream();
    EXPECT_FALSE(stream.acquireLatest(10).has_value());
}

// Latência baixa: com vários quadros prontos fica só o mais novo; os antigos voltam à fila.
TEST_F(CaptureStreamTest, acquireKeepsOnlyTheNewestFrame) {
    startStream();
    device.finishFrame();  // 0
    device.finishFrame();  // 1
    device.finishFrame();  // 2
    const auto frame = stream.acquireLatest(10);
    ASSERT_TRUE(frame.has_value());
    EXPECT_EQ(*frame, 2U);
    EXPECT_EQ(device.queued.size(), 3U);  // 3, 0, 1
    EXPECT_EQ(std::count(device.queued.begin(), device.queued.end(), 2U), 0);
}

TEST_F(CaptureStreamTest, releaseReturnsTheFrameToTheDriver) {
    startStream();
    device.finishFrame();
    const auto frame = stream.acquireLatest(10);
    ASSERT_TRUE(frame.has_value());
    ASSERT_TRUE(stream.release(*frame));
    EXPECT_EQ(device.queued.back(), *frame);
}

TEST_F(CaptureStreamTest, stopStopsStreamingAndFreesTheBuffers) {
    startStream();
    stream.stop();
    EXPECT_FALSE(device.streaming);
    EXPECT_EQ(device.bufferCount, 0U);
}

// ---- bombeamento captura -> RGA -> janela ----

struct FakeSink : FrameSink {
    std::optional<GraphicTarget> dequeue() override {
        if (!available) return std::nullopt;
        ++dequeued;
        return GraphicTarget{100, 1920, 1080, 1920, nullptr};
    }
    void queue(const GraphicTarget&) override { ++queued; }
    void cancel(const GraphicTarget&) override { ++cancelled; }
    bool available = true;
    int dequeued = 0, queued = 0, cancelled = 0;
};

struct FakeBlitter : Blitter {
    bool blit(int srcFd, const CaptureFormat& src, const GraphicTarget& dst) override {
        sources.push_back(srcFd);
        lastSrcWidth = src.width;
        lastDstFd = dst.fd;
        return succeed;
    }
    bool succeed = true;
    std::vector<int> sources;
    uint32_t lastSrcWidth = 0;
    int lastDstFd = -1;
};

class PreviewPumpTest : public CaptureStreamTest {
  protected:
    FakeSink sink;
    FakeBlitter blitter;
    PreviewPump pump{stream, sink, blitter};
};

TEST_F(PreviewPumpTest, frameGoesFromTheCaptureBufferToTheWindowByTheBlitter) {
    startStream();
    device.finishFrame();
    EXPECT_EQ(pump.runOnce(10), PreviewPump::Step::kFrame);
    ASSERT_EQ(blitter.sources.size(), 1U);
    EXPECT_EQ(blitter.sources[0], stream.dmabuf(0));
    EXPECT_EQ(blitter.lastSrcWidth, 1920U);
    EXPECT_EQ(blitter.lastDstFd, 100);
    EXPECT_EQ(sink.queued, 1);
    EXPECT_EQ(device.queued.size(), kBuffers);  // o buffer voltou ao driver
}

TEST_F(PreviewPumpTest, withoutFrameNothingIsDequeued) {
    startStream();
    EXPECT_EQ(pump.runOnce(10), PreviewPump::Step::kNoFrame);
    EXPECT_EQ(sink.dequeued, 0);
}

TEST_F(PreviewPumpTest, withoutWindowBufferTheFrameIsDropped) {
    startStream();
    sink.available = false;
    device.finishFrame();
    EXPECT_EQ(pump.runOnce(10), PreviewPump::Step::kNoTarget);
    EXPECT_EQ(device.queued.size(), kBuffers);
}

TEST_F(PreviewPumpTest, failedBlitCancelsTheWindowBuffer) {
    startStream();
    blitter.succeed = false;
    device.finishFrame();
    EXPECT_EQ(pump.runOnce(10), PreviewPump::Step::kBlitFailed);
    EXPECT_EQ(sink.cancelled, 1);
    EXPECT_EQ(sink.queued, 0);
    EXPECT_EQ(device.queued.size(), kBuffers);
}

// ---- reconfiguração quando a fonte muda de resolução ----

TEST(CaptureRestartTest, restartsOnlyWhenTheSignalChanged) {
    EXPECT_FALSE(needsRestart(CaptureSize{1920, 1080}, CaptureSize{1920, 1080}));
    EXPECT_TRUE(needsRestart(CaptureSize{1920, 1080}, CaptureSize{1280, 720}));
    EXPECT_TRUE(needsRestart(CaptureSize{1920, 1080}, std::nullopt));
}

}  // namespace
}  // namespace hy300::hdmiin
