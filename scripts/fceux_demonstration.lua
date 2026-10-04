-- Passive player recorder. No controller writes, save loads, or RAM writes.
local D = {active=false}
local directory = assert(os.getenv('SMB3_B2_DIRECTORY'))
local session = assert(os.getenv('SMB3_LIVE_SESSION_ID'))
local keys = {'A','B','up','down','left','right','start','select'}
function D.state()
  return {movie.framecount(), memory.readbyte(0x90)+256*memory.readbyte(0x75),
    memory.readbyte(0xA2)+256*memory.readbyte(0x87), memory.readbytesigned(0xBD),
    memory.readbytesigned(0xCF), memory.readbyte(0xED), memory.readbyte(0xD8),
    memory.readbyte(0x727), memory.readbyte(0x70A), memory.readbyte(0x77),
    memory.readbyte(0x79), memory.readbyte(0x14), memory.readbyte(0xF1),
    memory.readbyte(0x736), memory.readbyte(0x7967)}
end
local function capture()
  local image=io.open(directory..'/recording-'..D.id..'-'..movie.framecount()..'.gd','wb')
  if image then image:write(gui.gdscreenshot()); image:close() end
end
local function ack(status)
  local f = assert(io.open(directory..'/recording.ack','w'))
  f:write(D.id..' '..status); f:close()
end
function D.stop(reason)
  if D.active then capture(); D.active=false; D.file:flush(); D.file:close(); ack(reason) end
end
function D.poll(agent)
  local f = io.open(directory..'/recording.request','r')
  if f then
    local id, action, bound = f:read('*l'):match('^(%w+) (%w+) ([%w%-]+)$'); f:close()
    if id and action == 'play' and id ~= D.play_id and bound == session and not agent then
      D.play_id=id; emu.unpause()
    end
    if id and action == 'start' and id ~= D.id and bound == session and not agent then
      D.stop('superseded'); D.id=id
      D.file=assert(io.open(directory..'/recording-'..id..'.trace','w'))
      local state=D.state()
      D.active=true; D.count=0; D.expires=os.time()+600
      if state[8] ~= 0 or state[9] ~= 1 or state[10] ~= 1 or state[11] ~= 64 or state[12] ~= 0 or state[13] ~= 0 then D.stop('unsupported_entry')
      else capture(); ack('recording'); emu.unpause() end
    elseif id == D.id and action == 'stop' then D.stop('stopped') end
  end
  if D.active and (agent or os.time() >= D.expires) then D.stop(agent and 'ownership_changed' or 'timeout') end
end
function D.before() if D.active then D.pre=D.state() end end
function D.after()
  if not D.active or not D.pre then return end
  local mask=0; local input=joypad.get(1)
  for i,key in ipairs(keys) do if input[key] then mask=mask+2^(i-1) end end
  local post=D.state()
  D.file:write(table.concat(D.pre,',')..','..mask..','..post[2]..','..post[3]..'\n'); D.file:flush()
  D.count=D.count+1
  if D.count % 120 == 0 then capture() end
  if D.count >= 36000 or post[8] ~= 0 or post[9] ~= 1 or post[12] ~= 0 or post[14] < D.pre[14] then D.stop('segment_ended') end
end
return D
