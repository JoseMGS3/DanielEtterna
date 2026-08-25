local OUTPUT_FILE = "Save/DanielBridge.txt"


local function writeDanielState(song, steps)

    if song == nil then
        return
    end

    if steps == nil then
        steps = GAMESTATE:GetCurrentSteps()
    end


    local title = song:GetDisplayMainTitle() or ""
    local artist = song:GetDisplayArtist() or ""
    local song_dir = song:GetSongDir() or ""

    local difficulty = ""
    local meter = ""
    local stepstype = ""
    local description = ""
    local step_file = ""

    if steps ~= nil then

        difficulty = tostring(
            steps:GetDifficulty()
        )

        meter = tostring(
            steps:GetMeter()
        )

        stepstype = tostring(
            steps:GetStepsType()
        )

        description = (
            steps:GetDescription()
            or ""
        )

        step_file = (
            steps:GetFilename()
            or ""
        )

    end


    local rate = getCurRateValue()
	
	local msd_overall = 0
	local msd_stream = 0
	local msd_jumpstream = 0
	local msd_handstream = 0
	local msd_stamina = 0
	local msd_jackspeed = 0
	local msd_chordjack = 0
	local msd_technical = 0


	if steps ~= nil then

		local function safeMSD(index)

			local ok, value = pcall(function()
				return steps:GetMSD(rate, index)
			end)

			if ok and type(value) == "number" then
				return value
			end

			return 0
		end


		msd_overall = safeMSD(1)
		msd_stream = safeMSD(2)
		msd_jumpstream = safeMSD(3)
		msd_handstream = safeMSD(4)
		msd_stamina = safeMSD(5)
		msd_jackspeed = safeMSD(6)
		msd_chordjack = safeMSD(7)
		msd_technical = safeMSD(8)

	end


    local output =
		"bridge_version=4\n" ..
		"title=" .. title .. "\n" ..
		"artist=" .. artist .. "\n" ..
		"song_dir=" .. song_dir .. "\n" ..
		"step_file=" .. step_file .. "\n" ..
		"description=" .. description .. "\n" ..
		"difficulty=" .. difficulty .. "\n" ..
		"meter=" .. meter .. "\n" ..
		"stepstype=" .. stepstype .. "\n" ..
		"rate=" .. tostring(rate) .. "\n" ..
		"msd_overall=" .. tostring(msd_overall) .. "\n" ..
		"msd_stream=" .. tostring(msd_stream) .. "\n" ..
		"msd_jumpstream=" .. tostring(msd_jumpstream) .. "\n" ..
		"msd_handstream=" .. tostring(msd_handstream) .. "\n" ..
		"msd_stamina=" .. tostring(msd_stamina) .. "\n" ..
		"msd_jackspeed=" .. tostring(msd_jackspeed) .. "\n" ..
		"msd_chordjack=" .. tostring(msd_chordjack) .. "\n" ..
		"msd_technical=" .. tostring(msd_technical) .. "\n"


    File.Write(
        OUTPUT_FILE,
        output
    )

end



return Def.ActorFrame {

    BeginCommand = function(self)

        writeDanielState(
            GAMESTATE:GetCurrentSong(),
            GAMESTATE:GetCurrentSteps()
        )

    end,


    WheelSettledMessageCommand = function(self, params)

        if params and params.song then

            writeDanielState(
                params.song,
                params.steps
            )

        else

            writeDanielState(
                GAMESTATE:GetCurrentSong(),
                GAMESTATE:GetCurrentSteps()
            )

        end

    end,


    ChangedStepsMessageCommand = function(self, params)

        writeDanielState(
            GAMESTATE:GetCurrentSong(),
            params and params.steps
                or GAMESTATE:GetCurrentSteps()
        )

    end,


    CurrentRateChangedMessageCommand = function(self)

        writeDanielState(
            GAMESTATE:GetCurrentSong(),
            GAMESTATE:GetCurrentSteps()
        )

    end

}