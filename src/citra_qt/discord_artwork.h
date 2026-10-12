// Copyright 2026 Azahar Emulator Project
// Licensed under GPLv2 or any later version.

#pragma once

#include <algorithm>
#include <cstdint>
#include <iomanip>
#include <sstream>
#include <string>
#include "citra_qt/discord_artwork_catalog.h"

namespace DiscordRPC {

inline std::string GetGameArtworkUrl(std::uint64_t title_id) {
    const auto icon = std::lower_bound(GameArtworkCatalog.begin(), GameArtworkCatalog.end(), title_id,
                                      [](const auto& entry, auto id) { return entry.title_id < id; });
    if (icon == GameArtworkCatalog.end() || icon->title_id != title_id) {
        return {};
    }
    std::ostringstream url;
    url << GameArtworkBaseUrl << icon->category << '/' << std::uppercase << std::hex
        << std::setw(16) << std::setfill('0') << title_id << "/icon.jpg";
    return url.str();
}

} // namespace DiscordRPC
