local OUTPUT_FILE = "Save/DanielGameplay.txt"

-- 10 samples per second.
-- Python will interpolate between them to make the graph look smooth.
local UPDATE_INTERVAL = 0.10

local elapsed = 0


local function getRate()

    local ok, value = pcall(function()
        return getCurRateValue()
    end)

    if ok and type(value) == "number" then
        return value
    end

    return 1
end


local function writeState(playing)

    local seconds = 0

    local ok, value = pcall(function()
        return GAMESTATE:GetCurMusicSeconds()
    end)

    if ok and type(value) == "number" then
        seconds = value
    end


    local rate = getRate()


    local output =
        "playing=" .. (playing and "1" or "0") .. "\n" ..
        "music_seconds=" .. tostring(seconds) .. "\n" ..
        "rate=" .. tostring(rate) .. "\n"


    File.Write(
        OUTPUT_FILE,
        output
    )

end


return Def.ActorFrame {

    BeginCommand = function(self)

        elapsed = 0

        writeState(true)


        self:SetUpdateFunction(

            function(actor, delta)

                elapsed = elapsed + delta


                if elapsed >= UPDATE_INTERVAL then

                    elapsed = elapsed - UPDATE_INTERVAL

                    writeState(true)

                end

            end

        )

    end,


    OffCommand = function(self)

        writeState(false)

    end

}
