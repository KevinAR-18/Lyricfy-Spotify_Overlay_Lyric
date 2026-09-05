// JXA / Spotify scripting dictionary. duration is milliseconds; playerPosition
// is seconds. These assumptions must be verified in the native QA procedure.
ObjC.import("AppKit");

function snapshot() {
    // NSWorkspace queries running apps without starting Spotify or System Events.
    var apps = $.NSWorkspace.sharedWorkspace.runningApplications;
    var running = false;
    for (var i = 0; i < apps.count; i++) {
        if (ObjC.unwrap(apps.objectAtIndex(i).bundleIdentifier) === "com.spotify.client") {
            running = true;
            break;
        }
    }
    if (!running) return {version: 1, status: "not_running"};

    var spotify = Application("com.spotify.client");
    if (!spotify.running()) return {version: 1, status: "not_running"};
    function optional(read, fallback) {
        try { return read(); }
        catch (error) {
            if (Number(error.errorNumber) === -1743) throw error;
            return fallback;
        }
    }
    var state = spotify.playerState();
    if (state === "stopped") return {version: 1, status: "no_track"};
    if (state !== "playing" && state !== "paused") return {version: 1, status: "error"};
    var track = spotify.currentTrack;
    var title = optional(function () { return track.name(); }, "");
    if (!title) return {version: 1, status: "no_track"};
    var id = optional(function () { return track.id(); }, "");
    var artist = optional(function () { return track.artist(); }, "");
    var result = {
        id: id, title: title, artist: artist,
        album: optional(function () { return track.album(); }, ""),
        duration_ms: optional(function () { return track.duration(); }, 0),
        position_seconds: spotify.playerPosition(),
        is_playing: state === "playing",
        artwork_url: optional(function () { return track.artworkUrl(); }, "")
    };
    if (!spotify.running()) return {version: 1, status: "not_running"};
    if (state !== spotify.playerState() ||
        id !== optional(function () { return spotify.currentTrack.id(); }, "") ||
        title !== optional(function () { return spotify.currentTrack.name(); }, "") ||
        artist !== optional(function () { return spotify.currentTrack.artist(); }, "")) {
        return {version: 1, status: "changed"};
    }
    return {version: 1, status: "ok", track: result};
}

function run() {
    var result;
    try { result = snapshot(); }
    catch (error) {
        var code = Number(error.errorNumber);
        result = {version: 1, status: code === -1743 ? "permission_denied" :
            (code === -600 || code === -1728 ? "no_track" : "error")};
    }
    var output = JSON.stringify(result);
    return output.length > 32000 ? JSON.stringify({version: 1, status: "error"}) : output;
}
