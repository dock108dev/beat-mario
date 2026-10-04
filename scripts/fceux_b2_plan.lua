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
  if M.coin_route and M.completed_opening and memory.readbyte(0x70A) == 1
      and x() < 8192 and y() > 0 then
    event("coin_observation", "counter=" .. tostring(memory.readbyte(0x7967)))
  end
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
  M.jump_delay_frames = tonumber(initial.jump_delay_frames or "0")
  assert(M.jump_delay_frames >= 0 and M.jump_delay_frames <= 12 and M.jump_delay_frames % 1 == 0, "INVALID_JUMP_DELAY")
  M.delay_remaining = M.jump_delay_frames
  M.hop_frames = 0; M.hop_started = false; M.hop_done = false
  M.route_complete = false; M.last_lives = nil
  M.coin_route = M.path_choice == "coin_high" or M.path_choice == "coin_low" or M.path_choice == "coin_balanced"
  M.stairs_tactic = initial.stairs_tactic
  assert(not M.stairs_tactic or (M.stairs_tactic == "land_then_cross_v1" and M.path_choice == "coin_balanced"), "INVALID_ROUTE_GUIDANCE")
  M.stairs_done=false; M.stairs_phase=nil
  M.pipe_tactic=initial.pipe_tactic; M.pipe_done=false; M.pipe_phase=nil
  assert(not M.pipe_tactic or (M.pipe_tactic == "land_on_pipe_then_cross_v1" and M.stairs_tactic), "INVALID_PIPE_GUIDANCE")
  M.demo = nil; M.demo_index = nil
  if initial.demonstration_id then
    local frames = {}; local f = assert(io.open(directory .. "/demonstration.trace", "r"))
    for line in f:lines() do
      local row = {}; for value in line:gmatch("[^,]+") do row[#row+1] = assert(tonumber(value)) end
      assert(#row == 18, "INVALID_DEMONSTRATION_FRAME"); frames[#frames+1]=row
    end
    f:close(); assert(#frames == tonumber(initial.demonstration_frames), "INVALID_DEMONSTRATION_LENGTH")
    M.demo=frames; M.demo_id=initial.demonstration_id
  end
  speed(initial.speed)
  if M.coin_route then event("coin_route_applied", "route=" .. M.path_choice) end
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
    if M.coin_route then event("coin_observation", "counter=" .. tostring(memory.readbyte(0x7967))) end
  end
  if name == "world_1_1_exit" then
    M.completed_exit = true
    if M.coin_route then event("coin_level_finish_observed") end
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
  if M.coin_route and M.completed_opening and memory.readbyte(0x70A) == 1
      and x() < 8192 and y() > 0 then
    event("coin_observation", "counter=" .. tostring(memory.readbyte(0x7967)))
  end
  if M.demo and M.completed_opening then
    local state = {x(),y(),memory.readbytesigned(0xBD),memory.readbytesigned(0xCF),
      memory.readbyte(0xED),memory.readbyte(0xD8)}
    local function matches(row, tolerance)
      return math.abs(state[1]-row[2]) <= tolerance and math.abs(state[2]-row[3]) <= tolerance
        and math.abs(state[3]-row[4]) <= 4 and math.abs(state[4]-row[5]) <= 4
        and state[5] == row[6] and state[6] == row[7]
        and memory.readbyte(0x727) == row[8] and memory.readbyte(0x70A) == row[9]
        and memory.readbyte(0x77) == row[10] and memory.readbyte(0x79) == row[11]
        and memory.readbyte(0x14) == row[12] and memory.readbyte(0xF1) == 0
    end
    if not M.demo_index then
      if matches(M.demo[1], 8) then
        M.demo_index=1; event("demonstration_applied", "demonstration_id=" .. M.demo_id)
      elseif x() > M.demo[1][2]+24 then
        M.finish("demonstration_entry_missed"); error("GAME_COMPANION_B2_STOP_demonstration_entry_missed")
      end
    end
    if M.demo_index then
      if M.demo_index > #M.demo then
        local last=M.demo[#M.demo]
        if math.abs(x()-last[17]) > 24 or math.abs(y()-last[18]) > 24
            or memory.readbyte(0x727) ~= last[8] or memory.readbyte(0x70A) ~= last[9]
            or memory.readbyte(0xED) ~= last[6] or memory.readbyte(0xF1) ~= 0 then
          M.finish("demonstration_drift"); error("GAME_COMPANION_B2_STOP_demonstration_drift")
        end
        event("demonstration_sequence_completed", "demonstration_id=" .. M.demo_id)
        M.finish("completed_stop"); error("GAME_COMPANION_B2_STOP_completed_stop")
      end
      local row=M.demo[M.demo_index]
      if not matches(row,24) then M.finish("demonstration_drift"); error("GAME_COMPANION_B2_STOP_demonstration_drift") end
      local mask=row[16]
      for i,key in ipairs({"A","B","up","down","left","right","start","select"}) do
        held[key]=math.floor(mask/2^(i-1))%2 == 1
      end
      event("demonstration_frame", "demonstration_id=" .. M.demo_id .. " index=" .. M.demo_index)
      M.demo_index=M.demo_index+1
    end
  end
  M.held = held
  -- All eight buttons are specified: chat/physical key state cannot leak through
  -- unspecified keys in the Lua joypad override while agent authority is active.
  local input = {}
  for _,key in ipairs({"A","B","up","down","left","right","start","select"}) do input[key] = held[key] == true end
  joypad.set(1,input)
end
-- Stage on the left stair top before crossing the gap. The observed old
-- approach hit the stair face, lost speed, then fell short of the far platform.
function M.stairs_step(held, m)
  if M.stairs_tactic ~= "land_then_cross_v1" or M.stairs_done then return false end
  if not M.stairs_phase then
    if m.air ~= 0 or m.x < 1545 or m.x > 1600 then return false end
    M.stairs_phase = "release_climb"; M.stairs_frames = 0
    event("route_adjustment_applied", "adjustment=stage_on_left_stair")
  end
  M.stairs_frames = M.stairs_frames + 1
  if M.stairs_frames > 240 then
    M.finish("stairs_stalled"); error("GAME_COMPANION_B2_STOP_stairs_stalled")
  end
  held.left=false; held.right=true; held.A=false; held.B=false
  if M.stairs_phase == "release_climb" then
    M.stairs_phase = "climb"; M.stairs_airborne=false
  elseif M.stairs_phase == "climb" then
    held.A=true
    if m.air ~= 0 then M.stairs_airborne=true end
    if m.x >= 1580 then held.right=false; held.left=true; M.stairs_phase="settle" end
  elseif M.stairs_phase == "settle" then
    held.right=false
    -- Air momentum persists with no directional button. Counter-steer to
    -- zero velocity so the intended landing stays on the left stair top.
    local vx = memory.readbytesigned(0xBD)
    held.left = vx > 0; held.right = vx < 0
    if m.air == 0 and M.stairs_airborne then
      M.stairs_phase="cross"; M.cross_frames=0
      event("route_adjustment_applied", "adjustment=launch_from_stair_top")
    end
  elseif M.stairs_phase == "cross" then
    held.B=true; held.A=M.cross_frames < 42
    M.cross_frames=M.cross_frames+1
    if m.x >= 1750 and m.air == 0 and m.y < 400 then
      M.stairs_done=true
      event("route_progress_observed", "landmark=stairs_landing")
    end
  end
  return true
end
-- Preserve the height of the first pipe instead of waiting after walking off.
function M.pipe_step(held, m)
  if M.pipe_tactic ~= "land_on_pipe_then_cross_v1" or M.pipe_done or not M.stairs_done then return false end
  if not M.pipe_phase then
    if m.air ~= 0 or m.x < 1770 or m.x > 1810 then return false end
    M.pipe_phase="release"; M.pipe_frames=0
    event("route_adjustment_applied", "adjustment=stage_on_first_pipe")
  end
  M.pipe_frames=M.pipe_frames+1
  if M.pipe_frames > 240 then M.finish("pipe_stalled"); error("GAME_COMPANION_B2_STOP_pipe_stalled") end
  held.left=false; held.right=true; held.A=false; held.B=false
  if M.pipe_phase == "release" then
    M.pipe_phase="climb"; M.pipe_airborne=false
  elseif M.pipe_phase == "climb" then
    held.A=true
    if m.air ~= 0 then M.pipe_airborne=true end
    if m.x >= 1795 then held.right=false; held.left=true; M.pipe_phase="settle" end
  elseif M.pipe_phase == "settle" then
    local vx=memory.readbytesigned(0xBD)
    held.left=vx>0; held.right=vx<0
    if m.air == 0 and M.pipe_airborne then
      M.pipe_phase="runup"
      event("route_adjustment_applied", "adjustment=run_on_pipe_top")
    end
  elseif M.pipe_phase == "runup" then
    held.B=true
    if m.x >= 1812 then
      M.pipe_phase="cross"; M.pipe_cross_frames=0
      event("route_adjustment_applied", "adjustment=jump_from_pipe_top")
    end
  elseif M.pipe_phase == "cross" then
    held.B=true; held.A=M.pipe_cross_frames<42
    M.pipe_cross_frames=M.pipe_cross_frames+1
    if m.x >= 1930 and m.air == 0 and m.y < 400 then
      M.pipe_done=true; event("route_progress_observed", "landmark=pipe_landing")
    end
  end
  return true
end
function M.coin_window(position, windows)
  local offset = M.path_choice == "coin_high" and -20 or 20
  if M.path_choice == "coin_balanced" then offset = position < 700 and 0 or -8 end
  for _,w in ipairs(windows) do
    if position >= w[1] + offset and position <= w[2] + offset then return true end
  end
  return false
end
function M.coin_jump_frames(position)
  if M.path_choice == "coin_balanced" then return position < 700 and 18 or 22 end
  return M.path_choice == "coin_high" and 28 or 12
end
function M.opening_step(held)
  if M.path_choice ~= "opening_hop" then return false end
  if M.delay_remaining > 0 then
    held.right = true; held.A = false; held.B = false
    M.delay_remaining = M.delay_remaining - 1
    if M.delay_remaining == M.jump_delay_frames - 1 then
      event("coaching_delay_started", "jump_delay_frames=" .. tostring(M.jump_delay_frames))
    end
    return true
  end
  if not M.hop_started then
    M.hop_started = true; M.hop_frames = 26
    event("alternate_started", "primitive=world_1_1_opening_hop_v1 jump_delay_frames=" .. tostring(M.jump_delay_frames))
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
