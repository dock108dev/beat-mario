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
  if M.flight and M.completed_opening then M.flight_observe() end
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
  M.flight=nil
  if M.path_choice == "sky_hidden_1up" then
    assert(initial.flight_objective == "sky_hidden_1up_v2" and initial.stop_point == "world_1_1_hidden_1up"
      and (initial.speed == "1" or initial.speed == "1.0"), "INVALID_FLIGHT_OBJECTIVE")
    M.flight={phase="stage_runway",frames=0,objects={},popups={}}
    for slot=1,8 do M.flight.objects[slot]=memory.readbyte(0x660+slot)>0 end
    for i=0,4 do M.flight.popups[i]=memory.readbyte(0x79E+i) end
  end
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
      if M.flight or not valid_choice(c) or tonumber(c.revision) <= M.revision then
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
      if M.flight and c.speed == "turbo" then reject(c,"flight_requires_normal_speed")
      elseif c.speed == "1" or c.speed == "1.0" or c.speed == "turbo" then speed(c.speed == "turbo" and "turbo" or "1")
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
  if name == "world_1_1_flight_runway" then
    if not M.flight or memory.readbyte(0x727)~=0 or memory.readbyte(0x70A)~=1
        or x()<400 or x()>600 or y()<300 or y()>430 or memory.readbyte(0xD8)~=0
        or memory.readbyte(0xF1)~=0 or memory.readbyte(0x14)~=0
        or (memory.readbyte(0xED)~=3 and memory.readbyte(0xED)~=5) then
      M.finish("flight_prerequisite_missing"); error("GAME_COMPANION_B2_STOP_flight_prerequisite_missing")
    end
    M.completed_opening=true; M.last_lives=memory.readbyte(0x736)
    event("flight_objective_applied", "target=sky_hidden_1up_brick")
    M.flight_observe()
    return
  end
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
  if M.flight and M.completed_opening then
    M.flight_observe()
    if M.flight.collected then
      for _,key in ipairs({"A","B","up","down","left","right","start","select"}) do held[key]=false end
      if movie.framecount()>=M.flight.hit_frame+8 then
        M.finish("reward_hit_observed"); error("GAME_COMPANION_B2_STOP_reward_hit_observed")
      end
    end
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
-- Read-only reward observations: origin-latch the sky brick's 1UP,
-- then require its removal and newly emitted, colocated game-owned hit popup.
function M.flight_observe()
  if not M.flight or not M.completed_opening then return end
  local f = M.flight
  if f.last_observed_frame == movie.framecount() then return end
  f.last_observed_frame=movie.framecount()
  local newly_seen = {}
  for slot=1,8 do
    local state=memory.readbyte(0x660+slot)
    local id=memory.readbyte(0x670+slot)
    local ox=memory.readbyte(0x90+slot)+256*memory.readbyte(0x75+slot)
    local oy=memory.readbyte(0xA2+slot)+256*memory.readbyte(0x87+slot)
    if not f.slot and state > 0 and id == 11 and not f.objects[slot]
        and ox >= 1432 and ox <= 1448 and oy >= 112 and oy <= 144
        and x() >= 1404 and x() <= 1464 and y() <= 208 then
      f.slot=slot; event("flight_reward_revealed", "target=sky_hidden_1up_brick slot=" .. slot)
      local image=io.open(directory .. "/reward-revealed-" .. movie.framecount() .. ".gd", "wb")
      if image then image:write(gui.gdscreenshot()); image:close() end
    end
    newly_seen[slot]=state > 0
  end
  local slot=f.slot or 0
  local state=slot>0 and memory.readbyte(0x660+slot) or 0
  local id=slot>0 and memory.readbyte(0x670+slot) or 0
  local ox=slot>0 and memory.readbyte(0x90+slot)+256*memory.readbyte(0x75+slot) or 0
  local oy=slot>0 and memory.readbyte(0xA2+slot)+256*memory.readbyte(0x87+slot) or 0
  local popup=0
  local popups={}
  for i=0,4 do
    local value=memory.readbyte(0x79E+i)
    local counter=memory.readbyte(0x7A3+i)
    popups[i]=value
    if f.previous and f.previous.state>0 and state==0 then
      event("flight_popup_observation", "score_slot=" .. i .. " value=" .. value .. " counter=" .. counter
        .. " popup_x=" .. memory.readbyte(0x7AD+i) .. " popup_y=" .. memory.readbyte(0x7A8+i)
        .. " prior_sprite_x=" .. f.previous.sprite_x .. " prior_sprite_y=" .. f.previous.sprite_y)
    end
    if value == 13 and (counter == 48 or counter == 47) and f.popups[i] ~= 13 and f.previous
        and math.abs(memory.readbyte(0x7AD+i)-f.previous.sprite_x) <= 2
        and math.abs(memory.readbyte(0x7A8+i)-(((f.previous.sprite_y-16)%256>=192) and 5 or (f.previous.sprite_y-16)%256)) <= 2 then popup=1 end
  end
  local current={state=state,id=id,x=ox,y=oy,frame=movie.framecount(),
    sprite_x=slot>0 and memory.readbyte(0xAB+slot) or 0,
    sprite_y=slot>0 and memory.readbyte(0xB4+slot) or 0,
    mario_x=x(),mario_y=y(),lives=memory.readbyte(0x736),coins=memory.readbyte(0x7DA2),
    level_coins=memory.readbyte(0x7967),dying=memory.readbyte(0xF1)}
  event("flight_observation", "lives=" .. current.lives .. " coins=" .. current.coins
    .. " level_coins=" .. current.level_coins .. " dying=" .. (current.dying~=0 and "1" or "0")
    .. " form=" .. memory.readbyte(0xED) .. " p_meter=" .. memory.readbyte(0x3DD)
    .. " flight_timer=" .. memory.readbyte(0x56E) .. " slot=" .. (f.slot or -1)
    .. " object_state=" .. state .. " object_id=" .. id .. " object_x=" .. ox .. " object_y=" .. oy .. " popup=" .. popup)
  local prev=f.previous
  if prev and prev.frame == current.frame then return end
  if prev and f.slot and prev.frame+1 == current.frame and prev.id==11 and id==11
      and prev.state>0 and state==0 and popup==1 and prev.dying==0 and current.dying==0
      and math.abs(prev.mario_x-prev.x)<=24 and math.abs(prev.mario_y-prev.y)<=32
      and current.level_coins-prev.level_coins>=0 and current.level_coins-prev.level_coins<=1
      and current.coins==(prev.coins+current.level_coins-prev.level_coins)%100 then
    f.collected=true; f.hit_frame=movie.framecount()
    event("flight_reward_hit_observed", "target=sky_hidden_1up_brick")
    local image=io.open(directory .. "/reward-hit-" .. movie.framecount() .. ".gd", "wb")
    if image then image:write(gui.gdscreenshot()); image:close() end
  end
  f.previous=current; f.objects=newly_seen; f.popups=popups
end
function M.flight_step(held)
  if not M.flight then return false end
  local f=M.flight
  M.poll()
  if M.abort then error("GAME_COMPANION_B2_STOP_" .. M.abort) end
  if f.collected then
    for _,key in ipairs({"A","B","up","down","left","right","start","select"}) do held[key]=false end
    if movie.framecount()>=f.hit_frame+8 then
      M.finish("reward_hit_observed"); error("GAME_COMPANION_B2_STOP_reward_hit_observed")
    end
    return true
  end
  if memory.readbyte(0x727)~=0 or memory.readbyte(0x70A)~=1 or memory.readbyte(0x14)~=0 then
    M.finish("flight_area_changed"); error("GAME_COMPANION_B2_STOP_flight_area_changed")
  end
  local form=memory.readbyte(0xED)
  if form~=3 and form~=5 then M.finish("flight_form_lost"); error("GAME_COMPANION_B2_STOP_flight_form_lost") end
  f.frames=f.frames+1
  if f.frames>900 then M.finish("flight_budget_exhausted"); error("GAME_COMPANION_B2_STOP_flight_budget_exhausted") end
  for _,key in ipairs({"A","B","up","down","left","right","start","select"}) do held[key]=false end
  held.B=true
  if f.phase=="stage_runway" then
    -- Cross the short platforms and preparation shell by jumping onto the
    -- longer floor beyond the Leaf block. Brake before beginning the run-up.
    local vx=memory.readbytesigned(0xBD)
    held.right=x()<730; held.left=x()>=730 and vx>0
    held.A=x()<730 and (f.frames<24 or f.frames%4<2)
    held.B=x()<730 or f.frames%20<4
    if x()>=680 and x()<=780 and y()==368 and memory.readbyte(0xD8)==0 and math.abs(vx)<=2 then
      f.phase="runup"; f.runup_frame=f.frames; held.B=true; held.A=false; held.left=false; held.right=true
      event("flight_runway_staged", "landmark=long_floor")
    elseif x()>800 or f.frames>=240 then
      M.finish("flight_staging_failed"); error("GAME_COMPANION_B2_STOP_flight_staging_failed")
    end
  elseif f.phase=="runup" then
    held.right=true
    if memory.readbyte(0xD8)~=0 then
      M.finish("flight_runway_lost"); error("GAME_COMPANION_B2_STOP_flight_runway_lost")
    end
    if memory.readbyte(0x3DD)==127 and x()>=1032 then
      f.phase="fly"; f.launch_frame=f.frames; held.A=true
      event("flight_launch_applied", "p_meter=" .. memory.readbyte(0x3DD))
    elseif x()>=1060 or f.frames-(f.runup_frame or 0)>=240 then
      M.finish("flight_speed_missing"); error("GAME_COMPANION_B2_STOP_flight_speed_missing")
    end
    if f.phase=="runup" then
      -- Stop and spin while facing the approaching ground enemy. Charging
      -- through it made the tail hit window miss during real gameplay.
      for slot=1,8 do
        local state=memory.readbyte(0x660+slot)
        local id=memory.readbyte(0x670+slot)
        local ox=memory.readbyte(0x90+slot)+256*memory.readbyte(0x75+slot)
        local oy=memory.readbyte(0xA2+slot)+256*memory.readbyte(0x87+slot)
        if state>0 and state<4 and (id==109 or id==114) and ox-x()>=0 and ox-x()<=64
            and math.abs(oy-y())<=24 then
          f.phase="clear_runway"; f.clear_slot=slot; f.clear_frame=f.frames; f.clear_braked=false; f.clear_faced=false
          held.right=false; held.B=false
          event("flight_enemy_approach", "slot=" .. slot .. " enemy_x=" .. ox .. " enemy_y=" .. oy)
          break
        end
      end
    end
  elseif f.phase=="clear_runway" then
    local slot=f.clear_slot
    local state=memory.readbyte(0x660+slot)
    local ox=memory.readbyte(0x90+slot)+256*memory.readbyte(0x75+slot)
    held.B=(f.frames-f.clear_frame)%20>=3
    if state==0 or state>=4 then
      f.phase="runup"; f.runup_frame=f.frames; held.right=true; held.B=true
      event("flight_runway_cleared", "slot=" .. slot)
    elseif f.frames-f.clear_frame>120 then
      M.finish("flight_enemy_not_cleared"); error("GAME_COMPANION_B2_STOP_flight_enemy_not_cleared")
    elseif not f.clear_braked then
      held.B=false
      if memory.readbytesigned(0xBD)>0 then held.left=true
      else f.clear_braked=true end
    elseif not f.clear_faced then
      held.right=true; held.B=false; f.clear_faced=true; f.clear_frame=f.frames
    end
    if f.frames%4==0 then
      event("flight_enemy_observation", "enemy_x=" .. ox .. " state=" .. state
        .. " tail=" .. memory.readbyte(0x517) .. " vx=" .. memory.readbytesigned(0xBD)
        .. " pad=" .. memory.readbyte(0x17) .. " pressed=" .. memory.readbyte(0x18))
    end
  else
    local target=f.below_brick and 1432 or 1472
    if f.slot and memory.readbyte(0x660+f.slot)>0 then
      target=memory.readbyte(0x90+f.slot)+256*memory.readbyte(0x75+f.slot)
      if math.abs(target-1440)>160 then M.finish("reward_out_of_range"); error("GAME_COMPANION_B2_STOP_reward_out_of_range") end
    end
    local vx=memory.readbytesigned(0xBD)
    if math.abs(x()-target)<=8 then held.left=vx>0; held.right=vx<0
    else held.right=x()<target; held.left=x()>target end
    held.A=(f.frames-f.launch_frame)%4<2
    if not f.slot then
      if x()>=1464 then f.passed_brick=true end
      if f.passed_brick then
        held.A=false
        if y()>=144 and y()<430 then f.below_brick=true end
      end
      if f.below_brick and math.abs(x()-1432)<=8 then
        held.A=f.frames%20<10
      end
    else
      local oy=memory.readbyte(0xA2+f.slot)+256*memory.readbyte(0x87+f.slot)
      held.A=oy<y()-8 and (f.frames-f.launch_frame)%4<2
    end
    if memory.readbyte(0x56E)>0 and memory.readbyte(0xD8)~=0 and y()<300 and not f.observed then
      f.observed=true; event("flight_progress_observed", "landmark=flight")
    end
    if f.frames-f.launch_frame>240 and not f.observed then
      M.finish("flight_not_observed"); error("GAME_COMPANION_B2_STOP_flight_not_observed")
    end
  end
  return true
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
