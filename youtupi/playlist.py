import os, subprocess, threading, signal, time, re
from youtupi.video import Video
from youtupi.modules import local, youtube

player = None
videos = list()

def playingVideo():
    if isProcessRunning(player):
        viewedVideos = filter(lambda video:video.played==True, videos)
        lastPlayedVideo = viewedVideos[-1:]
        if lastPlayedVideo:
            return lastPlayedVideo[0]
    return None

def removeOldVideosFromPlaylist():
    viewedVideos = filter(lambda video:video.played==True, videos)
    currentVideo = playingVideo()
    for vv in viewedVideos:
        if vv != currentVideo:
            videos.remove(vv)

def removeVideo(videoId):
    video = findVideoInPlaylist(videoId)
    if video:
        if video == playingVideo():
            if len(videos) == 1:
                stopPlayer()
            else:
                playNextVideo()
        videos.remove(video)

def playList():
    return videos

def findVideoInPlaylist(vid):
    fvideos = filter(lambda video:video.vid==vid, videos)
    if fvideos:
        return fvideos[0]
    else:
        return None

def stopPlayer():
    global player
    if isProcessRunning(player):
        player.stdin.write("q")
        cont = 0
        while isProcessRunning(player):
            time.sleep(1)
            cont = cont + 1
            if cont > 10:
                os.killpg(player.pid, signal.SIGTERM)
                player = None

def playNextVideo():
    viewedVideos = filter(lambda video:video.played==False, videos)
    nextVideo = viewedVideos[:1]
    if nextVideo:
        try:
            playVideo(nextVideo[0].vid)
        except RuntimeError:
            print 'Error playing video'
            removeVideo(nextVideo[0].vid)

def addVideo(data):
    video = Video(data['id'], data)
    videos.append(video)

lock = threading.RLock()

TIMEOUT = 60

def playVideo(videoId):
    with lock:
        stopPlayer()
        svideo = findVideoInPlaylist(videoId)
        if svideo:
            if svideo != videos[0]:
                videos.remove(svideo)
                videos.insert(0, svideo)
                removeOldVideosFromPlaylist()
            cont = 0
            while not svideo.url:
                time.sleep(1)
                cont = cont + 1
                if cont > TIMEOUT:
                    raise RuntimeError('Error playing video: video not prepared')
            playerArgs = ["omxplayer", "-o", "hdmi"]
            playerArgs.append(svideo.url)
            print "Running player: " + " ".join(playerArgs)
            global player
            player = subprocess.Popen(playerArgs, stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.PIPE, preexec_fn=os.setsid)
            cont = 0
            while not isProcessRunning(player):
                time.sleep(1)
                cont = cont + 1
                if cont > TIMEOUT:
                    raise RuntimeError('Error playing video')
            svideo.data['started'] = int(time.time())
            svideo.played = True

def getVideoDuration(svideo):
    if svideo.url:
        args = ["omxplayer", "-i", svideo.url]
        omxplayeri = subprocess.Popen(args, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        (stout, sterr) = omxplayeri.communicate()
        if omxplayeri.returncode == 0:
            response = sterr.decode('UTF-8').strip()
            durationRegexp = re.compile(".+Duration: (\d+):(\d+):(\d+).+")
            durationSearch = durationRegexp.search(response)
            if durationSearch:
                return 3600 * int(durationSearch.group(1)) + 60 * int(durationSearch.group(2)) + int(durationSearch.group(3))
    return None

videoUrlLock = threading.RLock()

def prepareVideo(video):
    with videoUrlLock:        
        if not video.url:
            url = local.getUrl(video.data)
            if not url:
                url = youtube.getUrl(video.data)
            video.url = url
        if video.url and not video.data.get("duration", None):
            video.data["duration"] = getVideoDuration(video)

def autoPlay():
    removeOldVideosFromPlaylist()
    if videos:
        for nvideo in videos[:1]:
            prepareVideo(nvideo)
        if not isProcessRunning(player):
            playNextVideo()
        for nvideo in videos[:3]:
            prepareVideo(nvideo)
    threading.Timer(1, autoPlay).start()
    
def isProcessRunning(process):
    if process:
        if process.poll() == None:
            return True
    return False

def controlPlayer(action):
    global player
    if action == "stop":
        stopPlayer()
        global videos
        videos = list()
    if action == "pause":
        player.stdin.write("p")
    if action == "volup":
        player.stdin.write("+")
    if action == "voldown":
        player.stdin.write("-")
    if action == "forward":
        player.stdin.write("\x1B[C")
    if action == "backward":
        player.stdin.write("\x1B[D")

autoPlay()
