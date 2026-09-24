-- B2 bounded session plan controller. Only ordinary joypad input; no state writes.
-- gui.register also runs during paused redraws, so reclaim and wall-clock expiry
-- do not depend on advancing an emulated game frame.
local directory = assert(os.getenv("SMB3_B2_DIRECTORY"))
local session = assert(os.getenv("SMB3_LIVE_SESSION_ID"))
local reclaim_path = assert(os.getenv("SMB3_TAKEOVER_RECLAIM_PATH"))
local detach_path = assert(os.getenv("SMB3_LIVE_DETACH_PATH"))
local M = {active=false, paused=false, pending=nil, revision=0, next_sequence=1,
  completed_opening=false, completed_exit=false, held={}, stopped=false}

local function read_fields(path)
  local f = io.open(path, "r")
  if not f then return nil end
  local fields = {}
  for line in f:lines() do
    local k,v = string.match(line, "^([a-z_]+)=(.*)$")
    if k then fields[k] = v end
  end
  f:close()
  return fields
end
local function exists(path)
  local f = io.open(path, "r")
  if not f then return false end
  f:close()
  return true
end
local function x() return memory.readbyte(0x90) + memory.readbyte(0x75)*256 end
local function y() return memory.readbyte(0xA2) + memory.readbyte(0x87)*256 end
local function event(name, extra)
  local clock = read_fields(directory .. "/clock.request")
  local wall = clock and clock.wall or tostring(os.time())
  local f = io.open(directory .. "/events.log", "a")
  if not f then return end
  f:write("event=" .. name .. " epoch=" .. tostring(M.epoch or 0)
    .. " revision=" .. tostring(M.revision) .. " frame=" .. tostring(movie.framecount())
    .. " wall=" .. wall .. " x=" .. tostring(x()) .. " y=" .. tostring(y())
    .. (extra and (" " .. extra) or "") .. "\n")
  f:flush(); f:close()
  if name == "alternate_started" or name == "alternate_apex" or name == "alternate_rejoined"
      or name == "terminal" or name == "applied" then
    local image_dir = os.getenv("SMB3_LIVE_IMAGE_DIR")
    if image_dir then
      local image = io.open(image_dir .. "/" .. string.format("%09d",movie.framecount()) .. "_b2_" .. name .. ".gd", "wb")
      if image then image:write(gui.gdscreenshot()); image:close() end
    end
  end
end
local function neutral()
  local buttons = {}
  for _, k in ipairs({"A","B","up","down","left","right","start","select"}) do buttons[k] = false end
  joypad.set(1, buttons)
end
function M.force_neutral()
  neutral()
end
function M.confirm_neutral()
  -- joypad.get is the last completed frame's effective controller state.
  -- Call only after the wrapper advances an explicitly neutral frame.
  local actual = joypad.get(1)
  for _,button in ipairs({"A","B","up","down","left","right","start","select"}) do
    if actual[button] then
      event("neutralization_failed", "actual_button=" .. button)
      return false
    end
  end
  event("neutral_ack", "actual_buttons=none")
  return true
end
local function speed(rate)
  emu.speedmode(rate == "turbo" and "turbo" or "normal")
  M.speed = rate
  event("speed_ack", "speed=" .. rate)
end
local function reject(command, reason)
  event("rejected", "command_id=" .. tostring(command.command_id or "unknown") .. " reason=" .. reason)
end
function M.finish(reason)
  if M.stopped then return end
  neutral()
  local ok = pcall(emu.speedmode, "normal")
  M.paused = false
  M.abort = reason
  M.pending = nil
  M.stopped = true
  emu.unpause()
  event("terminal", "reason=" .. reason .. " speed_restored=" .. (ok and "1" or "0"))
end
function M.start(request)
  local initial = read_fields(directory .. "/initial.request")
  assert(initial and initial.session_id == session and initial.epoch == request.epoch,
    "GAME_COMPANION_B2_INVALID_AUTHORITY")
  M.active = true; M.stopped = false; M.abort = nil; M.paused = false
  M.epoch = tonumber(initial.epoch); M.revision = tonumber(initial.revision)
  M.seen = {}
  M.path_choice = initial.path_choice; M.stop_point = initial.stop_point
  M.expires = tonumber(initial.expires_epoch); M.next_sequence = 1
  M.pending = nil; M.completed_opening = false; M.completed_exit = false
  M.hop_frames = 0; M.hop_started = false; M.hop_done = false
  M.route_complete = false; M.last_lives = nil
  speed(initial.speed)
  event("started", "path_choice=" .. M.path_choice .. " stop_point=" .. M.stop_point)
  emu.unpause()
end
local function valid_choice(c)
  return (c.path_choice == "default" or c.path_choice == "opening_hop")
    and (c.stop_point == "full_route" or c.stop_point == "world_1_1_exit" or c.stop_point == "world_1_1_opening_end")
    and (c.path_choice ~= "opening_hop" or c.stop_point == "world_1_1_opening_end")
end
function M.poll()
  if not M.active or M.stopped then return end
  -- Reclaim is a separate signal and dominates every queued command.
  if exists(reclaim_path) or exists(detach_path) then M.finish("reclaimed"); return end
  if os.time() >= M.expires then M.finish("timeout"); return end
  if M.pending and os.time() >= tonumber(M.pending.deadline) then M.finish("boundary_wait_expired"); return end
  for _=1,32 do
    local c = read_fields(directory .. "/" .. tostring(M.epoch) .. "-" .. string.format("%06d", M.next_sequence) .. ".request")
    if not c then break end
    M.next_sequence = M.next_sequence + 1
    if M.seen[c.command_id] then
      reject(c,"duplicate_command")
    elseif c.session_id ~= session or tonumber(c.epoch) ~= M.epoch then
      reject(c,"wrong_session_or_epoch")
    elseif tonumber(c.sequence) ~= M.next_sequence - 1 then
      reject(c,"out_of_order")
    elseif tonumber(c.expected_revision) ~= M.revision then
      reject(c,"stale_revision")
    elseif c.action == "edit" then
      M.seen[c.command_id] = true
      if not valid_choice(c) or tonumber(c.revision) <= M.revision then
        reject(c,"invalid_primitive_or_revision")
      elseif M.pending and c.replace_pending ~= "1" then
        reject(c,"pending_requires_explicit_replace")
      elseif (c.boundary == "world_1_1_opening" and M.completed_opening)
          or (c.boundary == "world_1_1_exit" and M.completed_exit) then
        reject(c,"boundary_missed"); M.finish("boundary_missed"); return
      elseif c.boundary ~= "world_1_1_opening" and c.boundary ~= "world_1_1_exit" then
        reject(c,"unsupported_boundary")
      else
        if M.pending then event("superseded", "command_id=" .. M.pending.command_id) end
        M.pending = c
        event("queued", "command_id=" .. c.command_id .. " proposed_revision=" .. c.revision .. " boundary=" .. c.boundary)
      end
    elseif c.action == "cancel" then
      M.seen[c.command_id] = true
      if M.pending and M.pending.command_id == c.target_id then
        event("cancelled", "command_id=" .. M.pending.command_id); M.pending = nil
      else reject(c,"pending_change_no_longer_available") end
    elseif c.action == "speed" then
      M.seen[c.command_id] = true
      if c.speed == "1" or c.speed == "1.0" or c.speed == "turbo" then speed(c.speed == "turbo" and "turbo" or "1")
      else reject(c,"unsupported_speed") end
    elseif c.action == "pause" then
      M.seen[c.command_id] = true
      neutral(); M.paused = true; event("paused", "command_id=" .. c.command_id); emu.pause()
    elseif c.action == "resume" then
      M.seen[c.command_id] = true
      M.paused = false; event("resumed", "command_id=" .. c.command_id); emu.unpause()
    else reject(c,"unsupported_command") end
  end
end
function M.boundary(name)
  M.poll()
  if M.abort then error("GAME_COMPANION_B2_STOP_" .. M.abort) end
  if name == "world_1_1_opening" and (memory.readbyte(0x727) ~= 0
      or memory.readbyte(0x70A) ~= 1 or x() < 1 or x() > 64
      or y() < 1 or y() > 500 or memory.readbyte(0xF1) ~= 0) then
    M.finish("unsupported_entry"); error("GAME_COMPANION_B2_STOP_unsupported_entry")
  end
  if M.pending and M.pending.boundary == name then
    local c = M.pending
    if tonumber(c.expected_revision) ~= M.revision then M.finish("stale_revision"); error("GAME_COMPANION_B2_STOP_stale_revision") end
    neutral()
    M.revision = tonumber(c.revision); M.path_choice = c.path_choice; M.stop_point = c.stop_point
    M.pending = nil
    event("applied", "command_id=" .. c.command_id .. " boundary=" .. name .. " path_choice=" .. M.path_choice .. " stop_point=" .. M.stop_point)
  end
  event("boundary", "boundary=" .. name)
  if name == "world_1_1_opening" then
    M.completed_opening = true
    M.last_lives = memory.readbyte(0x736)
  end
  if name == "world_1_1_exit" then
    M.completed_exit = true
    if M.stop_point == "world_1_1_exit" then M.finish("completed_stop"); error("GAME_COMPANION_B2_STOP_completed_stop") end
  end
end
function M.before_frame(held)
  M.poll()
  if M.abort then error("GAME_COMPANION_B2_STOP_" .. M.abort) end
  if M.pending and M.pending.boundary == "world_1_1_opening" and M.completed_opening then
    M.finish("boundary_missed"); error("GAME_COMPANION_B2_STOP_boundary_missed")
  end
  -- F1 also marks nonfatal form changes. Match the cumulative route's actual
  -- death contract: a game-owned reduction of the life counter.
  local lives = memory.readbyte(0x736)
  if M.last_lives and lives < M.last_lives then M.finish("death"); error("GAME_COMPANION_B2_STOP_death") end
  if M.completed_opening then M.last_lives = lives end
  if M.stop_point == "world_1_1_opening_end" and M.completed_opening
      and memory.readbyte(0x70A) == 1 and x() >= 160 then
    M.finish("completed_stop"); error("GAME_COMPANION_B2_STOP_completed_stop")
  end
  M.held = held
  -- All eight buttons are specified: chat/physical key state cannot leak through
  -- unspecified keys in the Lua joypad override while agent authority is active.
  local input = {}
  for _,key in ipairs({"A","B","up","down","left","right","start","select"}) do input[key] = held[key] == true end
  joypad.set(1,input)
end
function M.opening_step(held)
  if M.path_choice ~= "opening_hop" then return false end
  if not M.hop_started then
    M.hop_started = true; M.hop_frames = 26
    event("alternate_started", "primitive=world_1_1_opening_hop_v1")
  end
  if M.hop_frames > 0 then
    if M.hop_frames == 13 then event("alternate_apex", "primitive=world_1_1_opening_hop_v1") end
    held.right = true; held.A = true; held.B = false
    M.hop_frames = M.hop_frames - 1
    return true
  end
  if not M.hop_done then
    M.hop_done = true; held.A = false
    event("alternate_rejoined", "primitive=world_1_1_opening_hop_v1")
  end
  return false
end
function M.audit_input()
  if not M.active or M.stopped or M.paused then return end
  local actual = joypad.get(1)
  local mismatch = false
  for _,button in ipairs({"A","B","up","down","left","right","start","select"}) do
    if (actual[button] == true) ~= (M.held[button] == true) then mismatch = true end
  end
  if mismatch then
    event("input_audit", "match=0")
    M.finish("input_isolation_failure")
  elseif movie.framecount() % 30 == 0 then event("input_audit", "match=1") end
end
function M.observe_event(name)
  if name == "post_probe_world_8_bowser_castle_stable_ending" then
    M.route_complete = true
    event("route_ending_observed")
  end
end
return M
