// Copyright 2018-2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the misc/licenses/gplv2.txt file included.

#include <chrono>
#include <string>
#include <discord_rpc.h>
#include "citra_qt/discord_artwork.h"
#include "citra_qt/discord_impl.h"
#include "citra_qt/uisettings.h"
#include "common/common_types.h"
#include "core/core.h"
#include "core/loader/loader.h"

namespace DiscordRPC {

DiscordImpl::DiscordImpl(const Core::System& system_) : system{system_} {
    DiscordEventHandlers handlers{};

    // Azahar's client ID supplies the images and default application name.
    Discord_Initialize("1345366770436800533", &handlers, 1, nullptr);
}

DiscordImpl::~DiscordImpl() {
    Discord_ClearPresence();
    Discord_Shutdown();
}

void DiscordImpl::Pause() {
    Discord_ClearPresence();
}

void DiscordImpl::Update(bool is_powered_on) {
    s64 start_time = std::chrono::duration_cast<std::chrono::seconds>(
                         std::chrono::system_clock::now().time_since_epoch())
                         .count();
    auto truncate = [](const std::string& str, std::size_t maxLen = 128) -> std::string {
        if (str.length() <= maxLen) {
            return str;
        }
        std::size_t end = maxLen - 3;
        while (end > 0 && (static_cast<unsigned char>(str[end]) & 0xC0) == 0x80) {
            --end;
        }
        return str.substr(0, end) + "...";
    };

    std::string title;
    std::string artwork;
    if (is_powered_on) {
        system.GetAppLoader().ReadTitle(title);
        u64 program_id{};
        if (system.GetAppLoader().ReadProgramId(program_id) == Loader::ResultStatus::Success) {
            artwork = GetGameArtworkUrl(program_id);
        }
    }
    // Discord adds the localized "Playing" label itself. Use the game title for
    // both the profile card heading and the compact member-list status.
    title = truncate(title.empty() ? "AzaharPlus" : title);

    DiscordRichPresence presence{};
    presence.name = title.c_str();
    presence.statusDisplayType = 0;
    presence.largeImageKey = artwork.empty() ? "logo" : artwork.c_str();
    presence.largeImageText = is_powered_on ? title.c_str() :
                                            "An open source emulator for the Nintendo 3DS";
    if (is_powered_on) {
        presence.details = "Nintendo 3DS / AzaharPlus";
    }
    presence.startTimestamp = start_time;
    Discord_UpdatePresence(&presence);
}
} // namespace DiscordRPC
