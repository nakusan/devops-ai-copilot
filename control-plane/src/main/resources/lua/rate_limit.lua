-- 令牌桶限流（原子）。
-- KEYS[1] = bucket key
-- ARGV[1] = now_ms
-- ARGV[2] = capacity（桶容量，约等于「每分钟允许请求数」）
-- ARGV[3] = refill_per_ms（每毫秒补充的令牌数 = capacity/60000）
-- ARGV[4] = cost（本次消耗，通常为 1）
-- 返回：1 通过；0 拒绝

local capacity = tonumber(ARGV[2])
local refill = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])
local now = tonumber(ARGV[1])

local data = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
local tokens = tonumber(data[1])
local last = tonumber(data[2])

if tokens == nil then
  tokens = capacity
  last = now
end

-- 按时间流逝补充令牌，但不超过容量
local delta = math.max(0, now - last)
tokens = math.min(capacity, tokens + delta * refill)

if tokens < cost then
  redis.call('HMSET', KEYS[1], 'tokens', tokens, 'ts', now)
  redis.call('EXPIRE', KEYS[1], 120)
  return 0
end

tokens = tokens - cost
redis.call('HMSET', KEYS[1], 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', KEYS[1], 120)
return 1
