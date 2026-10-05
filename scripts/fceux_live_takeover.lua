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
local b2_script = os.getenv("SMB3_B2_PLAN_SCRIPT")
local demo_script = os.getenv("SMB3_DEMONSTRATION_SCRIPT")
local demonstration = demo_script and dofile(demo_script) or nil
local b2 = b2_script and dofile(b2_script) or nil

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
      .. " air=" .. tostring(memory.readbyte(0xD8))
      .. " p_meter=" .. tostring(memory.readbyte(0x3DD))
      .. " flight_timer=" .. tostring(memory.readbyte(0x56E))
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

-- Explicit bounded preparation presses from the ordinary player interface.
-- Each press is session-bound, expires, neutralizes, then pauses for review.
local prep_directory = assert(os.getenv("SMB3_B2_DIRECTORY"))
local preparing
local prep = nil
local prep_nonce = nil
local function prep_finish(reason)
  if not prep then return end
  prep.remaining = 0
  prep.reason = reason
end
local function prep_poll()
  if prep then
    local detached = io.open(detach_path, "r")
    if detached then detached:close(); prep_finish("detached") end
    local reclaimed = io.open(reclaim_path, "r")
    if reclaimed then reclaimed:close(); prep_finish("reclaimed") end
    if os.time() >= prep.expires then prep_finish("expired") end
    return
  end
  if active_epoch or (b2 and b2.active) or (demonstration and demonstration.active) then return end
  local f = io.open(prep_directory .. "/preparation.request", "r")
  if not f then return end
  local nonce, bound, frames, expires, buttons = f:read("*l"):match("^(%w+) ([%w%-]+) (%d+) (%d+) ([%w,%-]+)$")
  f:close()
  if not nonce or nonce == prep_nonce then return end
  prep_nonce = nonce
  frames=tonumber(frames); expires=tonumber(expires)
  if bound ~= session_id or frames < 1 or frames > 60 or expires <= os.time() or expires > os.time()+4 then return end
  local held={}
  for button in buttons:gmatch("[^,]+") do
    if button ~= "none" then
      local valid=false
      for _, key in ipairs(ordered_buttons) do if button == key then valid=true end end
      if not valid then return end
      held[button]=true
    end
  end
  prep={nonce=nonce, remaining=frames, expires=expires, held=held, neutral=false}
  preparing=false
  emit("player", button_text(held), "preparation_press")
  emu.unpause()
end

-- GUI callbacks are invoked on paused redraws as well as game frames. This
-- deliberately uses no global keyboard events and keeps the command mailbox
-- and observer heartbeat responsive while the browser has focus.
local last_heartbeat = 0
preparing = os.getenv("SMB3_B2_PAUSE_FOR_PLAN") == "1"
if b2 then
  gui.register(function()
    prep_poll()
    if demonstration then
      local prior_play=demonstration.play_id
      demonstration.poll(b2.active or active_epoch ~= nil or prep ~= nil)
      if demonstration.play_id~=prior_play then
        -- Explicit player preparation releases the prior override. Recording
        -- remains passive; the controller owns this handoff.
        joypad.set(1, {}); preparing=false
      end
    end
    if preparing and demonstration and demonstration.active then preparing = false end
    if b2.active then b2.poll() end
    local request = command()
    if preparing and not prep and request and request.action == "start" and request.nonce ~= consumed_nonce then
      preparing = false
      emu.unpause()
    end
    if io.open(detach_path, "r") then emu.unpause() end
    if os.time() ~= last_heartbeat then
      last_heartbeat = os.time()
      if not (b2.active and b2.stopped) then
        emit(active_epoch and "agent" or "player", "", "idle_heartbeat")
      end
    end
  end)
  emu.registerbefore(function()
    if demonstration then demonstration.before() end
    if prep then
      prep_poll()
      local input = {}
      for _, button in ipairs(ordered_buttons) do input[button] = prep.remaining > 0 and prep.held[button] == true end
      joypad.set(1, input)
    elseif b2.active then
      local input = {}
      for _, button in ipairs(ordered_buttons) do
        input[button] = not b2.stopped and not b2.paused and b2.held[button] == true
      end
      joypad.set(1, input)
    end
  end)
  emu.registerafter(function()
    if demonstration then demonstration.after() end
    if prep then
      if prep.remaining > 0 then prep.remaining=prep.remaining-1
      elseif not prep.neutral then prep.neutral=true
      else
        local neutral=true
        for _, button in ipairs(ordered_buttons) do if joypad.get(1)[button] then neutral=false end end
        local f=assert(io.open(prep_directory.."/preparation.ack", "w"))
        f:write(prep.nonce.." "..(neutral and (prep.reason or "neutral") or "release_unconfirmed")); f:close()
        local image=assert(io.open(image_dir.."/"..string.format("%09d_preparation.gd", movie.framecount()), "wb"))
        image:write(gui.gdscreenshot()); image:close()
        emit("player", "", neutral and "preparation_neutral" or "preparation_release_unconfirmed")
        prep=nil; preparing=true; emu.pause()
      end
    end
    b2.audit_input()
  end)
end
if preparing then
  -- A fresh CPU may not have initialized cartridge RAM yet. Bootstrap only
  -- that cold state with neutral ordinary frames before freezing the review.
  if memory.readbyte(0x727) == 255 then
    local neutral = {}
    for _, button in ipairs(ordered_buttons) do neutral[button] = false end
    for _ = 1, 60 do joypad.set(1, neutral); emu.frameadvance() end
    joypad.set(1, {})
  end
  emit("player", "", "plan_review_paused")
  emu.pause()
end

while true do
  local detach = io.open(detach_path, "r")
  if detach ~= nil then
    detach:close()
    if demonstration then demonstration.stop("detached") end
    joypad.set(1, {})
    emit("player", "", "detached_neutral")
    if b2 then gui.register(nil); emu.registerbefore(nil); emu.registerafter(nil) end
    log:close()
    return
  end

  local request = command()
  if request ~= nil and request.action == "start"
      and request.nonce ~= consumed_nonce and active_epoch == nil and prep == nil then
    active_epoch = tonumber(request.epoch)
    consumed_nonce = request.nonce
    local supported_policy = request.policy == "world_1_1_remainder_v1"
      or request.policy == "world_8_finish_game_v1"
      or request.policy == "b2_world_1_1_plan_v1"
      or request.policy == "b2_full_route_plan_v1"
    emit("agent", "", "ownership_transferred")
    _G.SMB3_EMBEDDED_TAKEOVER = true
    _G.SMB3_EMBEDDED_TAKEOVER_POLICY = request.policy
    _G.SMB3_TAKEOVER_FRAME_CALLBACK = emit_agent_frame
    local bounded = b2 and (request.policy == "b2_world_1_1_plan_v1"
      or request.policy == "b2_full_route_plan_v1")
    if bounded then
      b2.start(request)
      _G.SMB3_B2_PLAN = b2
    end
    local succeeded = false
    local failure = "unsupported executable policy"
    if supported_policy then
      -- Lua 5.1 cannot yield through pcall/dofile. Resume an isolated coroutine
      -- and relay its frameadvance yield to FCEUX's main script coroutine.
      local chunk, load_failure = loadfile(agent_script)
      if chunk then
        local runner = coroutine.create(chunk)
        repeat
          succeeded, failure = coroutine.resume(runner)
          if not succeeded or coroutine.status(runner) == "dead" then break end
          coroutine.yield()
        until false
      else failure = load_failure end
    end
    if not succeeded then
      local failure_log = io.open(log_path .. ".controller-failure.txt", "a")
      if failure_log then failure_log:write(tostring(failure) .. "\n"); failure_log:close() end
    end
    if bounded and not b2.stopped then
      b2.finish(succeeded and b2.route_complete and "completed_route" or "controller_failure")
    end
    if bounded then
      -- Keep the B2 registerbefore override active for one complete neutral
      -- frame. An empty table would clear the mask back to pass-through, and
      -- an immediate joypad.get would mislabel cached agent input as player.
      b2.force_neutral()
      emu.frameadvance()
      if not b2.confirm_neutral() then
        error("GAME_COMPANION_B2_NEUTRALIZATION_UNCONFIRMED")
      end
    else
      joypad.set(1, {})
    end
    _G.SMB3_EMBEDDED_TAKEOVER = nil
    _G.SMB3_EMBEDDED_TAKEOVER_POLICY = nil
    _G.SMB3_TAKEOVER_FRAME_CALLBACK = nil
    _G.SMB3_B2_PLAN = nil
    if bounded then b2.active = false end
    if bounded and b2.abort ~= "completed_route" and b2.abort ~= "completed_stop" and b2.abort ~= "reward_hit_observed" then succeeded = false end
    if succeeded or (bounded and (b2.abort == "completed_stop" or b2.abort == "reward_hit_observed")) then
      emit("agent", "", "solution_returned_neutral")
    elseif (bounded and b2.abort == "reclaimed") or string.find(tostring(failure), "GAME_COMPANION_RECLAIM_REQUESTED", 1, true) then
      emit("player", "", "reclaimed_neutral")
    else
      emit("player", "", "solution_failed_neutral")
    end
    active_epoch = nil
    if bounded and b2.flight then
      -- Preserve the prepared form and timer while the player reviews the
      -- result. Authority is already revoked and neutral input acknowledged.
      joypad.set(1, {})
      preparing = true
      emu.pause()
    end
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
