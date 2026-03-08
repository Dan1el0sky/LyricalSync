import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Search, Loader2, Play, Pause, SkipBack, SkipForward, Volume2, Settings, Trash2, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import './index.css';

const API_BASE = 'http://localhost:8000';

function App() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [progressMsg, setProgressMsg] = useState("");
  const [progressPercent, setProgressPercent] = useState(0);

  const [showSettings, setShowSettings] = useState(false);
  const [mxmToken, setMxmToken] = useState("");
  const [geniusToken, setGeniusToken] = useState("");

  const [currentSong, setCurrentSong] = useState(null);
  const [songData, setSongData] = useState(null); // Lyrics & sync data
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);

  const audioRef = useRef(null);
  const progressBarRef = useRef(null);

  useEffect(() => {
    // Fetch settings on mount
    axios.get(`${API_BASE}/api/settings`).then(res => {
      setMxmToken(res.data.musixmatch_token || "");
      setGeniusToken(res.data.genius_token || "");
    }).catch(err => console.error(err));
  }, []);

  const saveSettings = async () => {
    try {
      await axios.post(`${API_BASE}/api/settings`, {
        musixmatch_token: mxmToken,
        genius_token: geniusToken
      });
      setShowSettings(false);
    } catch (err) {
      console.error(err);
    }
  };

  const clearDownloads = async () => {
    try {
      const res = await axios.delete(`${API_BASE}/api/downloads`);
      alert(`Deleted ${res.data.deleted} downloaded songs.`);
    } catch (err) {
      console.error(err);
    }
  };

  const searchSongs = async (e) => {
    e.preventDefault();
    if (!query) return;

    setLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/api/search`, { query });
      setResults(res.data.songs);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  const playSong = async (song) => {
    setResults([]);
    setCurrentSong(song);
    setSongData(null);
    setLoading(true);
    if (audioRef.current) {
      audioRef.current.pause();
      setIsPlaying(false);
    }


    setProgressMsg("Initializing...");
    setProgressPercent(0);

    let pollInterval = setInterval(async () => {
      try {
        const progRes = await axios.get(`${API_BASE}/api/progress/${song.videoId}`);
        if (progRes.data) {
          setProgressMsg(progRes.data.status);
          setProgressPercent(progRes.data.percent);
        }
      } catch (e) {}
    }, 1000);

    try {
      // 1. Process and get exact timings
      const res = await axios.post(`${API_BASE}/api/process`, {
        video_id: song.videoId,
        title: song.title,
        artist: song.artists[0]
      });

      clearInterval(pollInterval);
      setSongData(res.data);

      // 2. Load audio (serve static file from backend downloads folder using custom route, or we can use Blob)
      // For simplicity, we can fetch it or just point the audio tag if we serve the folder.
      // Wait, we need to serve downloads folder in main.py
    } catch (err) {
      clearInterval(pollInterval);
      console.error(err);
    }
    setLoading(false);
  };

  const togglePlay = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const onTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
      setDuration(audioRef.current.duration || 0);
    }
  };

  const handleSeek = (e) => {
    if (audioRef.current && duration > 0 && progressBarRef.current) {
      const rect = progressBarRef.current.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const newTime = (clickX / rect.width) * duration;
      audioRef.current.currentTime = newTime;
      setCurrentTime(newTime);
    }
  };

  const handleVolumeChange = (e) => {
    const newVolume = parseFloat(e.target.value);
    setVolume(newVolume);
    if (audioRef.current) {
      audioRef.current.volume = newVolume;
    }
  };

  const lyricsContainerRef = useRef(null);

  // Auto-scroll lyrics
  useEffect(() => {
    if (songData && lyricsContainerRef.current) {
      const activeElement = lyricsContainerRef.current.querySelector('.active-lyric');
      if (activeElement) {
        activeElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [currentTime, songData]);

  return (
    <div className="h-screen w-full flex flex-col bg-black text-white relative overflow-hidden font-sans">

      {/* Settings Modal */}
      {showSettings && (
        <div className="absolute inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-[#111] border border-white/10 rounded-2xl w-full max-w-md p-6 relative shadow-2xl">
            <button onClick={() => setShowSettings(false)} className="absolute top-4 right-4 text-gray-400 hover:text-white">
              <X size={24} />
            </button>
            <h2 className="text-2xl font-bold mb-6">Settings</h2>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-400 mb-2">Musixmatch User Token</label>
              <input
                type="text"
                value={mxmToken}
                onChange={e => setMxmToken(e.target.value)}
                className="w-full bg-black border border-white/10 rounded-lg p-3 text-white focus:border-green-500 outline-none"
                placeholder="Leave blank for anonymous token"
              />
            </div>

            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-400 mb-2">Genius Access Token</label>
              <input
                type="text"
                value={geniusToken}
                onChange={e => setGeniusToken(e.target.value)}
                className="w-full bg-black border border-white/10 rounded-lg p-3 text-white focus:border-green-500 outline-none"
                placeholder="Optional API token"
              />
            </div>

            <div className="flex gap-4">
              <button
                onClick={saveSettings}
                className="flex-1 bg-white text-black font-bold py-3 rounded-lg hover:bg-gray-200 transition"
              >
                Save Tokens
              </button>
              <button
                onClick={clearDownloads}
                className="flex items-center justify-center gap-2 bg-red-500/10 text-red-500 border border-red-500/20 px-4 rounded-lg hover:bg-red-500/20 transition"
                title="Delete all downloaded mp3 files"
              >
                <Trash2 size={20} />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Background Blur */}
      {currentSong && currentSong.thumbnail && (
        <div
          className="absolute inset-0 bg-cover bg-center opacity-30 blur-3xl transition-all duration-1000 scale-110"
          style={{ backgroundImage: `url(${currentSong.thumbnail})` }}
        />
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col z-10 p-6 overflow-hidden">

        {/* Top Header & Search Bar */}
        <div className="w-full max-w-4xl mx-auto mb-8 flex gap-4 items-center">
          <form onSubmit={searchSongs} className="relative flex items-center flex-1">
            <Search className="absolute left-4 text-gray-400" size={20} />
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search for any song..."
              className="w-full bg-white/10 border border-white/20 rounded-full py-4 pl-12 pr-4 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-green-500 backdrop-blur-md"
            />
          </form>
          <button
            onClick={() => setShowSettings(true)}
            className="w-14 h-14 flex items-center justify-center bg-white/10 border border-white/20 rounded-full hover:bg-white/20 transition backdrop-blur-md"
          >
            <Settings size={24} />
          </button>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto w-full max-w-6xl mx-auto flex relative">

          {/* Loading Indicator for Search */}
          {!currentSong && loading && results.length === 0 && (
            <div className="w-full flex justify-center mt-20">
              <Loader2 className="animate-spin text-green-500" size={48} />
            </div>
          )}

          {/* Results List Overlay */}
          {results.length > 0 && !loading && (
            <div className={`w-full ${currentSong ? 'absolute inset-0 z-40 bg-black/95 backdrop-blur-xl p-6 rounded-2xl overflow-y-auto border border-white/10' : ''}`}>
              {currentSong && (
                <div className="flex justify-between items-center mb-6">
                  <h2 className="text-2xl font-bold">Search Results</h2>
                  <button
                    onClick={() => setResults([])}
                    className="text-gray-400 hover:text-white"
                  >
                    <X size={24} />
                  </button>
                </div>
              )}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {results.map((song, idx) => (
                  <div
                    key={idx}
                    onClick={() => playSong(song)}
                    className="bg-white/5 hover:bg-white/10 p-4 rounded-xl cursor-pointer transition flex items-center gap-4 backdrop-blur-sm border border-white/5"
                  >
                    <img src={song.thumbnail} alt={song.title} className="w-16 h-16 rounded-md object-cover shadow-lg" />
                    <div className="flex-1 truncate">
                      <h3 className="font-bold text-lg truncate">{song.title}</h3>
                      <p className="text-gray-400 truncate">{song.artists.join(', ')}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Processing View */}
          {currentSong && loading && results.length === 0 && (
            <div className="flex-1 flex flex-col items-center justify-center max-w-lg mx-auto w-full">
              <Loader2 className="animate-spin text-green-500 mb-6" size={64} />
              <h3 className="text-2xl font-bold mb-2 text-center">{currentSong.title}</h3>
              <p className="text-xl font-medium text-green-400 mb-6 text-center">{progressMsg}</p>

              <div className="w-full h-3 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full bg-green-500 transition-all duration-500 ease-out"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
              <p className="text-gray-400 mt-4 text-center">This may take a moment depending on the song length.</p>
            </div>
          )}

          {currentSong && songData && (
            <div className="flex-1 flex flex-col md:flex-row gap-8 items-center md:items-start justify-center">
              {/* Album Art */}
              <div className="w-64 md:w-96 flex flex-col items-center">
                <motion.img
                  initial={{ scale: 0.9, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  src={currentSong.thumbnail}
                  alt="cover"
                  className="w-full aspect-square object-cover rounded-2xl shadow-2xl"
                />
                <h2 className="text-3xl font-bold mt-6 text-center">{currentSong.title}</h2>
                <p className="text-xl text-gray-400 mt-2">{currentSong.artists.join(', ')}</p>
              </div>

              {/* Lyrics View */}
              <div
                ref={lyricsContainerRef}
                className="flex-1 h-[60vh] md:h-full overflow-y-auto no-scrollbar relative w-full flex flex-col gap-6 py-[40vh] px-4"
              >
                {songData.alignment.segments.map((seg, idx) => {
                  const isPast = currentTime > seg.end;
                  const isActive = currentTime >= seg.start && currentTime <= seg.end;

                  if (seg.is_instrumental) {
                    return (
                      <motion.div
                        key={idx}
                        className={`text-4xl md:text-6xl font-black text-center transition-all duration-300 ${isActive ? 'active-lyric text-white opacity-100 scale-110' : (isPast ? 'text-white/40' : 'text-white/20')}`}
                      >
                        🎵
                      </motion.div>
                    );
                  }

                  return (
                    <div
                      key={idx}
                      className={`text-2xl md:text-5xl font-bold transition-all duration-300 ${isActive ? 'active-lyric text-white opacity-100 scale-105' : (isPast ? 'text-white/40' : 'text-white/20')} leading-tight`}
                    >
                      {seg.words.map((wordObj, widx) => {
                        const wordPast = currentTime > wordObj.end;
                        const wordActive = currentTime >= wordObj.start && currentTime <= wordObj.end;

                        return (
                          <span
                            key={widx}
                            className={`inline-block mr-2 transition-colors duration-150 ${wordPast ? 'text-white' : (wordActive ? 'text-green-400' : '')}`}
                          >
                            {/* Letter level precise effect within the active word using true backend timings */}
                            {wordObj.chars && wordObj.chars.length > 0 ?
                              wordObj.chars.map((charObj, cidx) => {
                                const charActive = currentTime >= charObj.start;

                                return (
                                  <span
                                    key={cidx}
                                    className={`transition-colors duration-75 ${charActive && wordActive ? 'text-green-400' : (wordPast ? 'text-white' : '')}`}
                                  >
                                    {charObj.char}
                                  </span>
                                )
                              })
                              :
                              wordObj.word.split('').map((char, cidx) => {
                                const charDuration = (wordObj.end - wordObj.start) / wordObj.word.length;
                                const charStart = wordObj.start + (cidx * charDuration);
                                const charActive = currentTime >= charStart;

                                return (
                                  <span
                                    key={cidx}
                                    className={`transition-colors duration-75 ${charActive && wordActive ? 'text-green-400' : (wordPast ? 'text-white' : '')}`}
                                  >
                                    {char}
                                  </span>
                                )
                              })
                            }
                          </span>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Player Bar */}
      {currentSong && (
        <div className="h-24 bg-black/80 backdrop-blur-xl border-t border-white/10 flex flex-col justify-center px-6 z-20 relative">

          {/* Progress Bar */}
          <div
            ref={progressBarRef}
            onClick={handleSeek}
            className="absolute top-0 left-0 right-0 h-1.5 bg-white/20 cursor-pointer hover:h-2 transition-all group z-30"
          >
            <div
              className="h-full bg-green-500 relative pointer-events-none"
              style={{ width: `${duration > 0 ? (currentTime / duration) * 100 : 0}%` }}
            >
              <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full opacity-0 group-hover:opacity-100 transition shadow-lg translate-x-1/2 pointer-events-none" />
            </div>
          </div>

          <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-4 w-1/3">
            <img src={currentSong.thumbnail} alt="cover" className="w-14 h-14 rounded-md object-cover" />
            <div>
              <p className="font-bold">{currentSong.title}</p>
              <p className="text-xs text-gray-400">{currentSong.artists.join(', ')}</p>
            </div>
          </div>

            <div className="flex flex-col items-center w-1/3">
              <div className="flex items-center gap-6">
                <button
                  onClick={() => { if(audioRef.current) audioRef.current.currentTime -= 10; }}
                  className="text-gray-400 hover:text-white transition"
                >
                  <SkipBack size={24} />
                </button>
                <button
                  onClick={togglePlay}
                  className="w-10 h-10 rounded-full bg-white text-black flex items-center justify-center hover:scale-105 transition"
                >
                  {isPlaying ? <Pause size={20} /> : <Play size={20} className="ml-1" />}
                </button>
                <button
                  onClick={() => { if(audioRef.current) audioRef.current.currentTime += 10; }}
                  className="text-gray-400 hover:text-white transition"
                >
                  <SkipForward size={24} />
                </button>
              </div>
            </div>

            <div className="w-1/3 flex justify-end items-center gap-3">
              <Volume2 className="text-gray-400" size={20} />
              <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={volume}
                onChange={handleVolumeChange}
                className="w-24 h-1 bg-gray-600 rounded-lg appearance-none cursor-pointer accent-white hover:accent-green-500 transition-all"
              />
            </div>

            <audio
              ref={audioRef}
              src={songData ? `${API_BASE}/downloads/${currentSong.videoId}.mp3` : ''}
              onTimeUpdate={onTimeUpdate}
              onLoadedMetadata={onTimeUpdate}
              onEnded={() => setIsPlaying(false)}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              autoPlay
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
