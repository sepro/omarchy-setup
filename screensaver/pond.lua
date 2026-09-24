-- Pond screensaver: also end on mouse movement, or when focus moves to a window
-- that isn't another screensaver (like Omarchy's text screensaver does). Wait a
-- moment first, so the window opening and taking focus doesn't count.
-- When one monitor's screensaver ends, close the others too.

local CLASS = "org.omarchy.screensaver"

local function end_all()
  mp.command_native({ name = "subprocess", args = { "pkill", "-f", "[o]rg.omarchy.screensaver" }, detach = true, playback_only = false })
  mp.command("quit")
end

local function focus_is_screensaver()
  local r = mp.command_native({ name = "subprocess", args = { "hyprctl", "activewindow", "-j" },
    capture_stdout = true, playback_only = false })
  return r.status == 0 and r.stdout:find('"class": "' .. CLASS .. '"', 1, true) ~= nil
end

mp.add_timeout(1.5, function()
  mp.add_forced_key_binding("MOUSE_MOVE", "pond-mouse-move", end_all)
  mp.observe_property("focused", "bool", function(_, focused)
    if focused == false and not focus_is_screensaver() then end_all() end
  end)
end)

mp.register_event("shutdown", function()
  mp.command_native({ name = "subprocess", args = { "pkill", "-f", "[o]rg.omarchy.screensaver" }, detach = true, playback_only = false })
end)
