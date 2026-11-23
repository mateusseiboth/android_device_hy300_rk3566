/*
 * SPDX-FileCopyrightText: 2026 Mateus Seiboth
 * SPDX-License-Identifier: Apache-2.0
 *
 * Testes da lógica do HAL de TV input do HY300 (entrada HDMI pelo RK628), no host.
 */

#include <gtest/gtest.h>

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>

#include "HdmiInCore.h"

namespace hy300::tvinput {
namespace {

namespace fs = std::filesystem;

class TempDir {
  public:
    TempDir() {
        std::string pattern = (fs::temp_directory_path() / "hy300-tvinput-XXXXXX").string();
        path_ = mkdtemp(pattern.data());
    }
    ~TempDir() { fs::remove_all(path_); }
    const fs::path& path() const { return path_; }
    void writeFile(const fs::path& relative, const std::string& content) const {
        fs::create_directories((path_ / relative).parent_path());
        std::ofstream(path_ / relative) << content;
    }

  private:
    fs::path path_;
};

TEST(HdmiInConfigTest, defaultsAreTheRk628ThroughRkisp) {
    const HdmiInConfig config = buildHdmiInConfig([](const char*) { return std::string(); });
    EXPECT_EQ(config.videoName, "rkisp_mainpath");
    EXPECT_EQ(config.subdevName, "rk628");
    EXPECT_EQ(config.audioAddress, "CARD_1_DEV_0");
    EXPECT_EQ(config.pollMs, 500);
}

TEST(HdmiInConfigTest, readsTheProperties) {
    const HdmiInConfig config = buildHdmiInConfig([](const char* name) -> std::string {
        const std::string key = name;
        if (key == "ro.vendor.hy300.hdmiin.video") return "stream_cif_mipi_id0";
        if (key == "ro.vendor.hy300.hdmiin.subdev") return "rk628-csi";
        if (key == "ro.vendor.hy300.hdmiin.audio_address") return "CARD_2_DEV_0";
        if (key == "ro.vendor.hy300.hdmiin.poll_ms") return "250";
        return "";
    });
    EXPECT_EQ(config.videoName, "stream_cif_mipi_id0");
    EXPECT_EQ(config.subdevName, "rk628-csi");
    EXPECT_EQ(config.audioAddress, "CARD_2_DEV_0");
    EXPECT_EQ(config.pollMs, 250);
}

TEST(HdmiInConfigTest, invalidPollFallsBack) {
    const HdmiInConfig config = buildHdmiInConfig([](const char* name) -> std::string {
        return std::string(name) == "ro.vendor.hy300.hdmiin.poll_ms" ? "0" : "";
    });
    EXPECT_EQ(config.pollMs, 500);
}

TEST(FindV4l2NodeTest, matchesByNameAndKind) {
    TempDir sys;
    sys.writeFile("video0/name", "rkisp_mainpath\n");
    sys.writeFile("video1/name", "rkisp_selfpath\n");
    sys.writeFile("v4l-subdev3/name", "m00_b_rk628-csi-v4l2 1-0050\n");
    sys.writeFile("v4l-subdev1/name", "rkisp-isp-subdev\n");
    EXPECT_EQ(findV4l2Node(sys.path(), "video", "rkisp_mainpath"), "video0");
    EXPECT_EQ(findV4l2Node(sys.path(), "v4l-subdev", "rk628"), "v4l-subdev3");
    EXPECT_FALSE(findV4l2Node(sys.path(), "video", "rk628").has_value());
}

TEST(StreamConfigTest, oneStreamWithTheDetectedTiming) {
    SignalState state;
    state.cablePresent = true;
    state.timing = Size{1920, 1080};
    const auto configs = buildStreamConfigs(state);
    ASSERT_EQ(configs.size(), 1U);
    EXPECT_EQ(configs[0].streamId, kStreamId);
    EXPECT_EQ(configs[0].width, 1920);
    EXPECT_EQ(configs[0].height, 1080);
}

TEST(StreamConfigTest, noTimingNoStream) {
    SignalState state;
    state.cablePresent = true;
    EXPECT_TRUE(buildStreamConfigs(state).empty());
}

TEST(CableStatusTest, followsThe5VDetection) {
    EXPECT_EQ(toCable(SignalState{true, std::nullopt}), Cable::kConnected);
    EXPECT_EQ(toCable(SignalState{false, std::nullopt}), Cable::kDisconnected);
}

TEST(HdmiInTrackerTest, firstStateIsAlwaysReported) {
    HdmiInTracker tracker;
    EXPECT_TRUE(tracker.update(SignalState{}));
}

TEST(HdmiInTrackerTest, reportsOnlyChanges) {
    HdmiInTracker tracker;
    tracker.update(SignalState{false, std::nullopt});
    EXPECT_FALSE(tracker.update(SignalState{false, std::nullopt}));
    EXPECT_TRUE(tracker.update(SignalState{true, std::nullopt}));
    EXPECT_TRUE(tracker.update(SignalState{true, Size{1280, 720}}));
    EXPECT_FALSE(tracker.update(SignalState{true, Size{1280, 720}}));
    EXPECT_TRUE(tracker.update(SignalState{true, Size{1920, 1080}}));
    EXPECT_EQ(tracker.current().timing->width, 1920);
}

TEST(SidebandTest, carriesMagicAndGeometry) {
    const auto ints = buildSidebandInts(Size{1920, 1080}, 0x3231564e /* NV12 */);
    ASSERT_EQ(ints.size(), 4U);
    EXPECT_EQ(ints[0], kSidebandMagic);
    EXPECT_EQ(ints[1], 1920);
    EXPECT_EQ(ints[2], 1080);
    EXPECT_EQ(static_cast<uint32_t>(ints[3]), 0x3231564eU);
}

}  // namespace
}  // namespace hy300::tvinput
