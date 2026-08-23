-- Game Companion V2.6 opt-in observer/controller. Observation-only launches
-- continue to use fceux_live_observer.lua, which contains no controller write.
local session_id = os.getenv("SMB3_LIVE_SESSION_ID")
local observer_token = os.getenv("SMB3_LIVE_OBSERVER_TOKEN")
local log_path = os.getenv("SMB3_LIVE_OBSERVER_LOG")
local detach_path = os.getenv("SMB3_LIVE_DETACH_PATH")
local image_dir = os.getenv("SMB3_LIVE_IMAGE_DIR")
local control_path = os.getenv("SMB3_TAKEOVER_CONTROL_PATH")
local reclaim_path = os.getenv("SMB3_TAKEOVER_RECLAIM_PATH")
local agent_script = os.getenv("SMB3_TAKEOVER_AGENT_SCRIPT")

if session_id == nil or observer_token == nil or log_path == nil
    or detach_path == nil or image_dir == nil or control_path == nil
    or reclaim_path == nil or agent_script == nil then
  error("Game Companion takeover observer requires complete session paths")
end

local log = assert(io.open(log_path, "w"))
local sequence = 0
local previous_buttons = ""
local previous_state = ""
local active_epoch = nil
local consumed_nonce = nil
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

local function command()
  local handle = io.open(control_path, "r")
  if handle == nil then return nil end
  local result = {}
  for line in handle:lines() do
    local key, value = string.match(line, "^([^=]+)=(.*)$")
    if key ~= nil then result[key] = value end
  end
  handle:close()
  return result
end

local function emit(actor, buttons, detail)
  sequence = sequence + 1
  log:write(
    "schema=game-companion-live-v1"
      .. " session=" .. session_id
      .. " token=" .. observer_token
      .. " seq=" .. tostring(sequence)
      .. " frame=" .. tostring(movie.framecount())
      .. " actor=" .. actor
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
      .. " control_epoch=" .. tostring(active_epoch or 0)
      .. " takeover_detail=" .. tostring(detail or "observation")
      .. " " .. item_fields()
      .. "\n"
  )
  log:flush()
end

local function emit_agent_frame(held)
  local buttons = button_text(held)
  local state = table.concat({
    tostring(memory.readbyte(0x727)), tostring(memory.readbyte(0x70A)),
    tostring(memory.readbyte(0x77)), tostring(memory.readbyte(0x79)),
    tostring(memory.readbyte(0x75)), tostring(player_x()), tostring(player_y()),
    tostring(memory.readbyte(0xED)), tostring(memory.readbyte(0x736)),
    tostring(memory.readbyte(0xF1)), tostring(memory.readbyte(0x14)),
  }, ",")
  if buttons ~= previous_buttons or state ~= previous_state or movie.framecount() % 15 == 0 then
    emit("agent", buttons, "authorized_solution_input")
    previous_buttons = buttons
    previous_state = state
  end
end

while true do
  local detach = io.open(detach_path, "r")
  if detach ~= nil then
    detach:close()
    joypad.set(1, {})
    emit("player", "", "detached_neutral")
    log:close()
    return
  end

  local request = command()
  if request ~= nil and request.action == "start"
      and request.nonce ~= consumed_nonce and active_epoch == nil then
    active_epoch = tonumber(request.epoch)
    consumed_nonce = request.nonce
    os.remove(reclaim_path)
    local supported_policy = request.policy == "world_1_1_remainder_v1"
      or request.policy == "world_8_finish_game_v1"
    emit("agent", "", "ownership_transferred")
    _G.SMB3_EMBEDDED_TAKEOVER = true
    _G.SMB3_EMBEDDED_TAKEOVER_POLICY = request.policy
    _G.SMB3_TAKEOVER_FRAME_CALLBACK = emit_agent_frame
    local succeeded = false
    local failure = "unsupported executable policy"
    if supported_policy then
      succeeded, failure = pcall(dofile, agent_script)
    end
    joypad.set(1, {})
    _G.SMB3_EMBEDDED_TAKEOVER = nil
    _G.SMB3_EMBEDDED_TAKEOVER_POLICY = nil
    _G.SMB3_TAKEOVER_FRAME_CALLBACK = nil
    if succeeded then
      emit("agent", "", "solution_returned_neutral")
    elseif string.find(tostring(failure), "GAME_COMPANION_RECLAIM_REQUESTED", 1, true) then
      emit("player", "", "reclaimed_neutral")
    else
      emit("player", "", "solution_failed_neutral")
    end
    active_epoch = nil
  end

  local input = joypad.get(1)
  local buttons = button_text(input)
  local state = table.concat({
    tostring(memory.readbyte(0x727)), tostring(memory.readbyte(0x70A)),
    tostring(memory.readbyte(0x77)), tostring(memory.readbyte(0x79)),
    tostring(memory.readbyte(0x75)), tostring(player_x()), tostring(player_y()),
    tostring(memory.readbyte(0xED)), tostring(memory.readbyte(0x736)),
    tostring(memory.readbyte(0xF1)), tostring(memory.readbyte(0x14)),
  }, ",")
  if buttons ~= previous_buttons or state ~= previous_state or movie.framecount() % 15 == 0 then
    emit("player", buttons, "observation")
    previous_buttons = buttons
    previous_state = state
  end
  if movie.framecount() % 300 == 0 then
    local image = assert(io.open(image_dir .. "/" .. string.format("%09d_live_state.gd", movie.framecount()), "wb"))
    image:write(gui.gdscreenshot())
    image:close()
  end
  emu.frameadvance()
end
