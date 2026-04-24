request = function()
  local id = math.random(1, 20000)
  return wrk.format("GET", "/api/products/" .. id)
end

