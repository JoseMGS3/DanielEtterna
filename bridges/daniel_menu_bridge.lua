local OUTPUT_FILE = "Save/DanielMenu.txt"

local UPDATE_INTERVAL = 0.05
local elapsed = 0


local function getRate()

    local ok, value = pcall(function()
        return getCurRateValue()
    end)

    if ok and type(value) == "number" and value > 0 then
        return value
    end

    return 1
end


local function getMusicSeconds()

    local ok, value = pcall(function()
        return GAMESTATE:GetCurMusicSeconds()
    end)

    if ok and type(value) == "number" then
        return value
    end

    return 0
end


local function getSampleStart()

    local song = GAMESTATE:GetCurrentSong()

    if song == nil then
        return 0
    end

    local ok, value = pcall(function()
        return song:GetSampleStart()
    end)

    if ok and type(value) == "number" then
        return value
    end

    return 0
end


local function writeMenuState()

    local song = GAMESTATE:GetCurrentSong()

    if song == nil then
        return
    end

    local output =
        "music_seconds=" .. tostring(getMusicSeconds()) .. "\n" ..
        "sample_start=" .. tostring(getSampleStart()) .. "\n" ..
        "rate=" .. tostring(getRate()) .. "\n"

    File.Write(
        OUTPUT_FILE,
        output
    )
end


return Def.ActorFrame {

    BeginCommand = function(self)

        elapsed = 0

        writeMenuState()

        -- Esta es la parte importante:
        -- el archivo se reescribe continuamente mientras
        -- ScreenSelectMusic esta activo, no solo cuando
        -- cambia la cancion.
        self:SetUpdateFunction(
            function(actor, delta)

                elapsed = elapsed + delta

                if elapsed >= UPDATE_INTERVAL then

                    elapsed = elapsed - UPDATE_INTERVAL

                    writeMenuState()
                end
            end
        )
    end,


    WheelSettledMessageCommand = function(self)

        elapsed = 0
        writeMenuState()
    end,


    ChangedStepsMessageCommand = function(self)

        writeMenuState()
    end,


    CurrentRateChangedMessageCommand = function(self)

        writeMenuState()
    end
}
