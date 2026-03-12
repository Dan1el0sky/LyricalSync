import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Search, Loader2, Play, Pause, SkipBack, SkipForward, Volume2, Settings, Trash2, X, Music, ListMusic, Plus } from 'lucide-react';
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
  const [songData, setSongData] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);

  // Queue state
  const [queue, setQueue] = useState([]);
  const [queueIndex, setQueueIndex] = useState(-1);
  const [showQueue, setShowQueue] = useState(false);

  const audioRef = useRef(null);
  const progressBarRef = useRef(null);
  const lyricsContainerRef = useRef(null);

  useEffect(() => {
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

  const processAndPlaySong = async (song) => {
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
      const res = await axios.post(`${API_BASE}/api/process`, {
        video_id: song.videoId,
        title: song.title,
        artist: song.artists[0]
      });

      clearInterval(pollInterval);
      setSongData(res.data);
    } catch (err) {
      clearInterval(pollInterval);
      console.error(err);
      setProgressMsg("Failed to process song.");
    }
    setLoading(false);
  };

  const playNow = (song) => {
    setResults([]);
    setShowQueue(false);
    // If it's already in the queue, just set index. Otherwise, clear queue and start fresh.
    setQueue([song]);
    setQueueIndex(0);
    processAndPlaySong(song);
  };

  const addToQueue = (song, e) => {
    e.stopPropagation(); // prevent playNow from firing
    setQueue(prev => [...prev, song]);
    if (queue.length === 0 && !currentSong) {
      setQueueIndex(0);
      processAndPlaySong(song);
    }
    setResults([]);
  };

  const skipForward = () => {
    if (queueIndex < queue.length - 1) {
      const nextIndex = queueIndex + 1;
      setQueueIndex(nextIndex);
      processAndPlaySong(queue[nextIndex]);
    }
  };

  const skipBackward = () => {
    if (currentTime > 3 || queueIndex === 0) {
      // Just restart current song
      if (audioRef.current) audioRef.current.currentTime = 0;
    } else if (queueIndex > 0) {
      // Go to previous song
      const prevIndex = queueIndex - 1;
      setQueueIndex(prevIndex);
      processAndPlaySong(queue[prevIndex]);
    }
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

  useEffect(() => {
    if (songData && lyricsContainerRef.current) {
      const activeElement = lyricsContainerRef.current.querySelector('.active-lyric');
      if (activeElement) {
        activeElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [currentTime, songData]);

  const formatTime = (time) => {
    if (isNaN(time)) return "0:00";
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
  };

  return (
    <div className="h-screen w-full flex flex-col bg-[#050505] text-white relative overflow-hidden font-sans selection:bg-fuchsia-500/30">

      {/* Dynamic Blurred Background */}
      <AnimatePresence>
        {currentSong?.thumbnail && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.4 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 1.5 }}
            className="absolute inset-0 bg-cover bg-center blur-[120px] scale-125 z-0 saturate-200"
            style={{ backgroundImage: `url(${currentSong.thumbnail})` }}
          />
        )}
      </AnimatePresence>
      <div className="absolute inset-0 bg-gradient-to-t from-black via-black/50 to-transparent z-0 pointer-events-none" />

      {/* Settings Modal */}
      <AnimatePresence>
        {showSettings && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 z-50 bg-black/80 backdrop-blur-xl flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.9, opacity: 0, y: 20 }}
              className="bg-white/10 border border-white/20 rounded-3xl w-full max-w-md p-8 relative shadow-[0_0_50px_rgba(0,0,0,0.5)] backdrop-blur-2xl"
            >
              <button onClick={() => setShowSettings(false)} className="absolute top-6 right-6 text-white/50 hover:text-white transition-colors">
                <X size={24} />
              </button>
              <h2 className="text-3xl font-black mb-8 tracking-tight">Preferences</h2>

              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-bold text-white/70 mb-2 uppercase tracking-wider">Musixmatch Token</label>
                  <input
                    type="text"
                    value={mxmToken}
                    onChange={e => setMxmToken(e.target.value)}
                    className="w-full bg-black/50 border border-white/10 rounded-xl p-4 text-white focus:border-fuchsia-500 focus:ring-1 focus:ring-fuchsia-500 outline-none transition-all placeholder:text-white/20"
                    placeholder="Leave blank for anonymous token"
                  />
                </div>

                <div>
                  <label className="block text-sm font-bold text-white/70 mb-2 uppercase tracking-wider">Genius Token</label>
                  <input
                    type="text"
                    value={geniusToken}
                    onChange={e => setGeniusToken(e.target.value)}
                    className="w-full bg-black/50 border border-white/10 rounded-xl p-4 text-white focus:border-fuchsia-500 focus:ring-1 focus:ring-fuchsia-500 outline-none transition-all placeholder:text-white/20"
                    placeholder="Optional API token"
                  />
                </div>
              </div>

              <div className="flex gap-4 mt-8">
                <button
                  onClick={saveSettings}
                  className="flex-1 bg-white text-black font-bold py-4 rounded-xl hover:bg-gray-200 transition-colors active:scale-[0.98]"
                >
                  Save Changes
                </button>
                <button
                  onClick={clearDownloads}
                  className="flex items-center justify-center w-14 bg-red-500/20 text-red-500 border border-red-500/30 rounded-xl hover:bg-red-500/30 transition-colors active:scale-[0.98]"
                  title="Clear Cache"
                >
                  <Trash2 size={20} />
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* App Header & Search */}
      <div className="z-10 flex flex-col px-6 md:px-12 pt-8 pb-4 w-full max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3 select-none">
            <div className="w-10 h-10 bg-gradient-to-br from-fuchsia-500 to-cyan-500 rounded-xl flex items-center justify-center shadow-lg shadow-fuchsia-500/20">
              <Music size={20} className="text-white" />
            </div>
            <h1 className="text-2xl font-black tracking-tighter">LyricalSync</h1>
          </div>
          <button
            onClick={() => setShowSettings(true)}
            className="w-12 h-12 flex items-center justify-center bg-white/5 border border-white/10 rounded-full hover:bg-white/15 transition-colors backdrop-blur-md text-white/70 hover:text-white"
          >
            <Settings size={22} />
          </button>
        </div>

        <form onSubmit={searchSongs} className="relative w-full max-w-2xl mx-auto group">
          <Search className="absolute left-6 top-1/2 -translate-y-1/2 text-white/40 group-focus-within:text-fuchsia-400 transition-colors" size={22} />
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search songs, artists, or albums..."
            className="w-full bg-white/5 border border-white/10 hover:border-white/20 rounded-2xl py-5 pl-16 pr-6 text-lg font-medium text-white placeholder-white/30 focus:outline-none focus:bg-white/10 focus:border-white/30 transition-all backdrop-blur-xl shadow-2xl"
          />
        </form>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-hidden w-full max-w-7xl mx-auto z-10 relative flex flex-col">

        {/* Loading State */}
        <AnimatePresence>
          {loading && !songData && (
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="absolute inset-0 flex flex-col items-center justify-center bg-black/40 backdrop-blur-sm rounded-3xl z-30"
            >
              <div className="w-24 h-24 mb-8 relative">
                <div className="absolute inset-0 rounded-full border-t-2 border-fuchsia-500 animate-spin opacity-70"></div>
                <div className="absolute inset-2 rounded-full border-r-2 border-cyan-500 animate-spin-slow opacity-70"></div>
                <div className="absolute inset-4 rounded-full border-b-2 border-white animate-spin-reverse opacity-70"></div>
              </div>

              {currentSong ? (
                <div className="text-center w-full max-w-md px-6">
                  <h3 className="text-2xl font-bold mb-2 truncate">{currentSong.title}</h3>
                  <p className="text-fuchsia-400 font-medium mb-6 animate-pulse">{progressMsg}</p>
                  <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-fuchsia-500 to-cyan-500 transition-all duration-300 ease-out"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                </div>
              ) : (
                <p className="text-white/50 font-medium">Searching the database...</p>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Search Results */}
        <AnimatePresence>
          {results.length > 0 && !loading && (
            <motion.div
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 20 }}
              className="absolute inset-0 z-40 overflow-y-auto no-scrollbar pb-32 px-6 md:px-12"
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 pb-8">
                {results.map((song, idx) => (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.05 }}
                    key={idx}
                    onClick={() => playNow(song)}
                    className="bg-white/5 hover:bg-white/10 p-3 rounded-2xl cursor-pointer transition-all duration-300 flex items-center justify-between backdrop-blur-md border border-white/5 hover:border-white/20 group hover:-translate-y-1 shadow-lg hover:shadow-xl hover:shadow-fuchsia-500/10"
                  >
                    <div className="flex items-center gap-4 flex-1 min-w-0 pr-2">
                      <div className="relative w-16 h-16 rounded-xl overflow-hidden shrink-0 shadow-md group-hover:shadow-fuchsia-500/30 transition-shadow">
                        <img src={song.thumbnail} alt={song.title} className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500" />
                        <div className="absolute inset-0 bg-black/20 group-hover:bg-black/0 transition-colors flex items-center justify-center">
                          <Play className="opacity-0 group-hover:opacity-100 transition-opacity text-white drop-shadow-md" size={24} fill="currentColor" />
                        </div>
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="font-bold text-base truncate text-white/90 group-hover:text-white">{song.title}</h3>
                        <p className="text-sm text-white/50 truncate mt-0.5">{song.artists.join(', ')}</p>
                      </div>
                    </div>

                    <button
                      onClick={(e) => addToQueue(song, e)}
                      className="w-10 h-10 rounded-full bg-white/5 hover:bg-white/20 flex items-center justify-center transition-colors shrink-0 text-white/50 hover:text-white border border-white/10"
                      title="Add to Queue"
                    >
                      <Plus size={20} />
                    </button>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Queue Drawer */}
        <AnimatePresence>
          {showQueue && (
            <motion.div
              initial={{ opacity: 0, x: 300 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 300 }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
              className="absolute right-0 top-0 bottom-0 w-full md:w-96 bg-black/80 backdrop-blur-3xl border-l border-white/10 z-50 flex flex-col pt-8 pb-32"
            >
              <div className="flex items-center justify-between px-6 mb-6">
                <h2 className="text-2xl font-black tracking-tight flex items-center gap-2">
                  <ListMusic size={24} className="text-fuchsia-500" />
                  Queue
                </h2>
                <button onClick={() => setShowQueue(false)} className="text-white/50 hover:text-white p-2 bg-white/5 hover:bg-white/10 rounded-full transition-colors">
                  <X size={20} />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto px-4 no-scrollbar">
                {queue.length === 0 ? (
                  <div className="text-center text-white/40 mt-10">
                    <p>Your queue is empty.</p>
                    <p className="text-sm mt-2">Search for songs and click + to add them.</p>
                  </div>
                ) : (
                  <div className="flex flex-col gap-2">
                    {queue.map((qSong, i) => {
                      const isPlayingIdx = i === queueIndex;
                      return (
                        <div
                          key={i}
                          onClick={() => {
                            setQueueIndex(i);
                            processAndPlaySong(queue[i]);
                          }}
                          className={`flex items-center gap-4 p-3 rounded-xl cursor-pointer transition-all ${isPlayingIdx ? 'bg-gradient-to-r from-fuchsia-500/20 to-cyan-500/20 border border-fuchsia-500/30' : 'bg-white/5 hover:bg-white/10 border border-transparent'}`}
                        >
                          <div className="w-12 h-12 rounded-lg overflow-hidden shrink-0 relative">
                            <img src={qSong.thumbnail} alt={qSong.title} className="w-full h-full object-cover" />
                            {isPlayingIdx && (
                              <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                                <div className="w-1.5 h-1.5 bg-white rounded-full animate-bounce"></div>
                              </div>
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <h4 className={`font-bold text-sm truncate ${isPlayingIdx ? 'text-fuchsia-400' : 'text-white/90'}`}>{qSong.title}</h4>
                            <p className="text-xs text-white/50 truncate">{qSong.artists.join(', ')}</p>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Active Player View (Lyrics & Cover) */}
        <AnimatePresence>
          {currentSong && songData && results.length === 0 && !showQueue && (
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex-1 flex flex-col lg:flex-row h-full overflow-hidden"
            >
              {/* Left Column: Artwork */}
              <div className="w-full lg:w-[45%] flex flex-col items-center justify-center p-8 lg:p-12 shrink-0 h-[40vh] lg:h-full relative z-20">
                <motion.div
                  initial={{ scale: 0.9, y: 20, opacity: 0 }}
                  animate={{ scale: 1, y: 0, opacity: 1 }}
                  transition={{ type: "spring", stiffness: 200, damping: 20 }}
                  className="w-full max-w-[280px] sm:max-w-[320px] lg:max-w-[420px] aspect-square relative group"
                >
                  <div className="absolute inset-0 bg-black/20 rounded-[2rem] translate-y-4 blur-2xl group-hover:blur-3xl transition-all duration-500"></div>
                  <img
                    src={currentSong.thumbnail}
                    alt="cover"
                    className="w-full h-full object-cover rounded-[2rem] shadow-2xl relative z-10 border border-white/10"
                  />
                  {/* Decorative vinyl reflection effect */}
                  <div className="absolute inset-0 rounded-[2rem] bg-gradient-to-tr from-white/0 via-white/10 to-white/0 opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none z-20"></div>
                </motion.div>

                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.2 }}
                  className="mt-10 text-center w-full max-w-md px-4"
                >
                  <h2 className="text-3xl lg:text-5xl font-black tracking-tight mb-3 truncate px-2 text-white/90">{currentSong.title}</h2>
                  <p className="text-lg lg:text-xl font-medium text-white/50 truncate">{currentSong.artists.join(', ')}</p>
                </motion.div>
              </div>

              {/* Right Column: Lyrics */}
              <div className="w-full lg:w-[55%] h-[60vh] lg:h-full relative overflow-hidden">
                <div
                  ref={lyricsContainerRef}
                  className="h-full overflow-y-auto no-scrollbar flex flex-col py-[50vh] px-6 lg:px-12 items-start"
                  style={{
                    maskImage: 'linear-gradient(to bottom, transparent, black 15%, black 85%, transparent)',
                    WebkitMaskImage: 'linear-gradient(to bottom, transparent, black 15%, black 85%, transparent)'
                  }}
                >
                  {songData.alignment.segments.map((seg, idx) => {
                    const isPast = currentTime > seg.end;
                    const isActive = currentTime >= seg.start && currentTime <= seg.end;
                    const isUpcoming = currentTime < seg.start;

                    if (seg.is_instrumental) {
                      return (
                        <div
                          key={`inst-${idx}`}
                          className={`w-full py-8 transition-all duration-700 ease-[cubic-bezier(0.2,0.8,0.2,1)] flex items-center gap-4 ${isActive ? 'active-lyric opacity-100' : (isPast ? 'opacity-30' : 'opacity-20')}`}
                        >
                          <div className={`h-[2px] flex-1 rounded-full ${isActive ? 'bg-gradient-to-r from-fuchsia-500 to-transparent' : 'bg-white/20'}`}></div>
                          <Music size={24} className={isActive ? 'text-fuchsia-400 animate-bounce' : 'text-white'} />
                          <div className={`h-[2px] flex-1 rounded-full ${isActive ? 'bg-gradient-to-l from-cyan-500 to-transparent' : 'bg-white/20'}`}></div>
                        </div>
                      );
                    }

                    return (
                      <div
                        key={idx}
                        className={`text-3xl sm:text-4xl lg:text-[2.75rem] font-bold transition-all duration-500 ease-[cubic-bezier(0.2,0.8,0.2,1)] py-4 lg:py-6 origin-left leading-[1.3] w-full
                          ${isActive ? 'active-lyric opacity-100 scale-[1.02] text-white drop-shadow-[0_0_15px_rgba(255,255,255,0.3)]' :
                           (isPast ? 'opacity-40 text-white/80 scale-100 blur-[0.5px]' :
                                     'opacity-20 text-white/60 scale-95 blur-[1px]')}`}
                      >
                        {seg.words.map((wordObj, widx) => {
                          const wordPast = currentTime > wordObj.end;
                          const wordActive = currentTime >= wordObj.start && currentTime <= wordObj.end;

                          return (
                            <span key={widx} className="inline-block mr-[0.25em] relative">
                              {/* Character level highlight */}
                              {wordObj.chars && wordObj.chars.length > 0 ? (
                                wordObj.chars.map((charObj, cidx) => {
                                  const charActive = currentTime >= charObj.start;
                                  return (
                                    <span
                                      key={cidx}
                                      className={`transition-colors duration-150 ${charActive ? 'text-white drop-shadow-[0_0_8px_rgba(255,255,255,0.8)]' : (isActive ? 'text-white/40' : '')}`}
                                      style={{
                                        color: charActive && isActive ? '#fff' : undefined,
                                        textShadow: charActive && isActive ? '0 0 20px rgba(255,255,255,0.5), 0 0 10px #d946ef' : 'none'
                                      }}
                                    >
                                      {charObj.char}
                                    </span>
                                  )
                                })
                              ) : (
                                wordObj.word.split('').map((char, cidx) => {
                                  const charDuration = (wordObj.end - wordObj.start) / wordObj.word.length;
                                  const charStart = wordObj.start + (cidx * charDuration);
                                  const charActive = currentTime >= charStart;
                                  return (
                                    <span
                                      key={cidx}
                                      className={`transition-colors duration-150`}
                                      style={{
                                        color: charActive && isActive ? '#fff' : (isActive ? 'rgba(255,255,255,0.4)' : undefined),
                                        textShadow: charActive && isActive ? '0 0 20px rgba(255,255,255,0.5), 0 0 10px #d946ef' : 'none'
                                      }}
                                    >
                                      {char}
                                    </span>
                                  )
                                })
                              )}
                            </span>
                          );
                        })}
                      </div>
                    );
                  })}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Floating Bottom Player */}
      <AnimatePresence>
        {currentSong && (
          <motion.div
            initial={{ y: 100, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="fixed bottom-6 left-1/2 -translate-x-1/2 w-[calc(100%-3rem)] max-w-4xl h-24 bg-black/60 backdrop-blur-3xl border border-white/10 rounded-[2rem] flex flex-col justify-center px-6 z-[60] shadow-2xl"
          >
            {/* Minimal Progress Bar overlaying top of player */}
            <div
              ref={progressBarRef}
              onClick={handleSeek}
              className="absolute top-0 left-6 right-6 h-1 bg-white/10 cursor-pointer rounded-full overflow-hidden group/bar hover:h-2 transition-all duration-300 transform -translate-y-1/2"
            >
              <div
                className="h-full bg-gradient-to-r from-fuchsia-500 to-cyan-500 relative pointer-events-none"
                style={{ width: `${duration > 0 ? (currentTime / duration) * 100 : 0}%` }}
              >
                <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full opacity-0 group-hover/bar:opacity-100 transition-opacity shadow-[0_0_10px_white] translate-x-1/2" />
              </div>
            </div>

            <div className="flex items-center justify-between h-full pt-1 relative">
              {/* Left: Mobile/Compact Info */}
              <div className="flex items-center gap-4 z-10 w-1/4 sm:w-1/3">
                <img src={currentSong.thumbnail} alt="cover" className="w-12 h-12 rounded-xl object-cover shadow-md border border-white/10 lg:hidden shrink-0" />
                <div className="flex flex-col min-w-0">
                  <span className="text-xs font-bold text-white/50 w-12 font-mono tracking-wider">{formatTime(currentTime)}</span>
                </div>
              </div>

              {/* Center: Controls (Absolutely Positioned for Perfect Centering) */}
              <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center justify-center gap-4 sm:gap-6 z-20">
                <button
                  onClick={skipBackward}
                  className={`transition-colors active:scale-95 ${queueIndex > 0 || currentTime > 3 ? 'text-white hover:text-fuchsia-400' : 'text-white/20 cursor-not-allowed'}`}
                >
                  <SkipBack size={24} fill="currentColor" className="opacity-80" />
                </button>

                <button
                  onClick={togglePlay}
                  className="w-14 h-14 rounded-full bg-white text-black flex items-center justify-center hover:scale-105 active:scale-95 transition-all shadow-[0_0_20px_rgba(255,255,255,0.3)] hover:shadow-[0_0_30px_rgba(255,255,255,0.5)] shrink-0"
                >
                  {isPlaying ? <Pause size={24} fill="currentColor" /> : <Play size={24} fill="currentColor" className="ml-1" />}
                </button>

                <button
                  onClick={skipForward}
                  className={`transition-colors active:scale-95 ${queueIndex < queue.length - 1 ? 'text-white hover:text-fuchsia-400' : 'text-white/20 cursor-not-allowed'}`}
                >
                  <SkipForward size={24} fill="currentColor" className="opacity-80" />
                </button>
              </div>

              {/* Right: Volume & Time & Queue Toggle */}
              <div className="flex justify-end items-center gap-3 sm:gap-4 z-10 w-1/4 sm:w-1/3">
                <span className="text-xs font-bold text-white/50 font-mono tracking-wider hidden sm:block">{formatTime(duration)}</span>

                <button
                  onClick={() => setShowQueue(!showQueue)}
                  className={`p-2 rounded-full transition-colors shrink-0 ${showQueue ? 'bg-fuchsia-500/20 text-fuchsia-400' : 'bg-white/5 text-white/50 hover:bg-white/10 hover:text-white'}`}
                  title="Queue"
                >
                  <ListMusic size={18} />
                </button>

                <div className="hidden lg:flex items-center gap-2 w-28 group/vol relative">
                  <Volume2 className="text-white/50 group-hover/vol:text-white/80 transition-colors shrink-0" size={18} />
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.01"
                    value={volume}
                    onChange={handleVolumeChange}
                    className="w-full h-1 bg-white/20 rounded-full appearance-none cursor-pointer accent-white hover:accent-fuchsia-500 transition-all"
                  />
                </div>
              </div>

              <audio
                ref={audioRef}
                src={songData ? `${API_BASE}/downloads/${currentSong.videoId}.mp3` : ''}
                onTimeUpdate={onTimeUpdate}
                onLoadedMetadata={onTimeUpdate}
                onEnded={() => {
                  setIsPlaying(false);
                  skipForward(); // Auto-play next in queue
                }}
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                autoPlay
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default App;
