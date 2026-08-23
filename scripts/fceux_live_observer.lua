-- Game Companion V2.4 passive observer. This file intentionally exposes no
-- joypad.set, memory.write, reset, power-on, savestate, or state-load path.
local session_id = os.getenv("SMB3_LIVE_SESSION_ID")
local observer_token = os.getenv("SMB3_LIVE_OBSERVER_TOKEN")
local log_path = os.getenv("SMB3_LIVE_OBSERVER_LOG")
local detach_path = os.getenv("SMB3_LIVE_DETACH_PATH")
local image_dir = os.getenv("SMB3_LIVE_IMAGE_DIR")

if session_id == nil or observer_token == nil or log_path == nil
    or detach_path == nil or image_dir == nil then
  error("Game Companion live observer requires session, token, log, detach, and image paths")
end

local log = assert(io.open(log_path, "w"))
local sequence = 0
local previous_buttons = ""
local previous_state = ""
local ordered_buttons = {"A", "B", "up", "down", "left", "right", "start", "select"}

local function player_x()
  return memory.readbyte(0x90) + memory.readbyte(0x75) * 256
end

local function player_y()
  return memory.readbyte(0xA2) + memory.readbyte(0x87) * 256
end

local function button_text(input)
  local pressed = {}
  for _, button in ipairs(ordered_buttons) do
    if input[button] then pressed[#pressed + 1] = button end
  end
  return table.concat(pressed, ",")
end

local function item_fields()
  local values = {}
  for index = 0, 9 do
    values[#values + 1] = "item_" .. tostring(index) .. "="
      .. tostring(memory.readbyte(0x7D80 + index))
  end
  return table.concat(values, " ")
end

while true do
  local detach = io.open(detach_path, "r")
  if detach ~= nil then
    detach:close()
    log:flush()
    log:close()
    return
  end

  local frame = movie.framecount()
  local input = joypad.get(1)
  local buttons = button_text(input)
  local state = table.concat({
    tostring(memory.readbyte(0x727)),
    tostring(memory.readbyte(0x70A)),
    tostring(memory.readbyte(0x77)),
    tostring(memory.readbyte(0x79)),
    tostring(memory.readbyte(0x75)),
    tostring(player_x()),
    tostring(player_y()),
    tostring(memory.readbyte(0xED)),
    tostring(memory.readbyte(0x736)),
    tostring(memory.readbyte(0xF1)),
    tostring(memory.readbyte(0x14)),
  }, ",")

  if buttons ~= previous_buttons or state ~= previous_state or frame % 15 == 0 then
    sequence = sequence + 1
    log:write(
      "schema=game-companion-live-v1"
        .. " session=" .. session_id
        .. " token=" .. observer_token
        .. " seq=" .. tostring(sequence)
        .. " frame=" .. tostring(frame)
        .. " actor=player"
        .. " buttons=" .. buttons
        .. " world=" .. tostring(memory.readbyte(0x727))
        .. " object_set=" .. tostring(memory.readbyte(0x70A))
        .. " map_page=" .. tostring(memory.readbyte(0x77))
        .. " map_cursor_x=" .. tostring(memory.readbyte(0x79))
        .. " map_cursor_y=" .. tostring(memory.readbyte(0x75))
        .. " x=" .. tostring(player_x())
        .. " y=" .. tostring(player_y())
        .. " form=" .. tostring(memory.readbyte(0xED))
        .. " lives=" .. tostring(memory.readbyte(0x736))
        .. " dying=" .. tostring(memory.readbyte(0xF1) ~= 0 and 1 or 0)
        .. " return_map=" .. tostring(memory.readbyte(0x14))
        .. " " .. item_fields()
        .. "\n"
    )
    log:flush()
    previous_buttons = buttons
    previous_state = state
  end
  if frame % 300 == 0 then
    local image = assert(io.open(
      image_dir .. "/" .. string.format("%09d_live_state.gd", frame), "wb"
    ))
    image:write(gui.gdscreenshot())
    image:close()
  end
  emu.frameadvance()
end
